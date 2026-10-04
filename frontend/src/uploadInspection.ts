import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = workerUrl

export class UploadProblem extends Error {
  constructor(
    public code:
      | 'uploadSize'
      | 'uploadInvalid'
      | 'uploadEncrypted'
      | 'uploadPages'
      | 'uploadNoText',
  ) {
    super(code)
  }
}

export async function inspectUpload(
  file: File,
  limits: { max_upload_mb: number; max_pdf_pages: number },
): Promise<number> {
  if (file.size > limits.max_upload_mb * 1024 * 1024) throw new UploadProblem('uploadSize')
  const header = new TextDecoder().decode(await file.slice(0, 5).arrayBuffer())
  if (header !== '%PDF-') throw new UploadProblem('uploadInvalid')
  const task = getDocument({
    data: new Uint8Array(await file.arrayBuffer()),
    isEvalSupported: false,
  })
  let encrypted = false
  task.onPassword = () => {
    encrypted = true
    void task.destroy().catch(() => {})
  }
  try {
    const pdf = await task.promise
    if (pdf.numPages < 1 || pdf.numPages > limits.max_pdf_pages)
      throw new UploadProblem('uploadPages')
    for (let number = 1; number <= pdf.numPages; number++) {
      const page = await pdf.getPage(number)
      const content = await page.getTextContent()
      const hasText = content.items.some((item) => 'str' in item && item.str.trim())
      page.cleanup()
      if (hasText) return pdf.numPages
    }
    throw new UploadProblem('uploadNoText')
  } catch (error) {
    if (encrypted) throw new UploadProblem('uploadEncrypted')
    if (error instanceof UploadProblem) throw error
    throw new UploadProblem('uploadInvalid')
  } finally {
    await task.destroy()
  }
}
