/** Export instructional captions over an actual recording without changing playback speed. */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = new URL('../', import.meta.url)
const tutorialPath = new URL('docs/media/demo-tutorial.json', root)

function clock(seconds, separator = '.') {
  const milliseconds = Math.round(seconds * 1000)
  const h = Math.floor(milliseconds / 3600000)
  const m = Math.floor(milliseconds / 60000) % 60
  const s = Math.floor(milliseconds / 1000) % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}${separator}${String(milliseconds % 1000).padStart(3, '0')}`
}

export function probeMedia(filename, cwd) {
  const info = JSON.parse(
    execFileSync(
      'ffprobe',
      [
        '-v',
        'error',
        '-show_entries',
        'format=duration:stream=codec_name,width,height,pix_fmt',
        '-of',
        'json',
        filename,
      ],
      { cwd, encoding: 'utf8' },
    ),
  )
  return { duration_seconds: Number(info.format.duration), ...info.streams[0] }
}

export async function exportDemoMedia(recording, output, images) {
  const tutorial = JSON.parse(await readFile(tutorialPath, 'utf8'))
  const raw = probeMedia('live-recording.webm', output)
  if (raw.width !== 1440 || raw.height !== 900)
    throw new Error('Expected a 1440 × 900 raw recording.')
  const duration = Math.min(
    recording.duration_seconds,
    raw.duration_seconds - recording.trimmed_initial_navigation_seconds,
  )
  if (!(duration > 0)) throw new Error('The raw recording has no usable frames.')
  await mkdir(images, { recursive: true })
  const media = {}
  for (const language of tutorial.languages) {
    const suffix = language === 'en' ? '' : '.zh-TW'
    const cues = recording.scenes
      .filter((scene) => scene.start_seconds < duration)
      .map((scene, index) => {
        const content = tutorial.scenes[scene.id]?.[language]
        if (!content) throw new Error(`Missing ${language} tutorial for scene ${scene.id}.`)
        for (const value of Object.values(content)) {
          if (/[{}\\\n\r]/.test(value))
            throw new Error('Caption text must not contain ASS override syntax.')
        }
        return {
          start: scene.start_seconds,
          end: Math.min(recording.scenes[index + 1]?.start_seconds ?? duration, duration),
          ...content,
        }
      })
    const text = (cue) => `${cue.title}\n${cue.action}\n${cue.note}`
    await writeFile(
      `${output}/ragglass-demo${suffix}.srt`,
      cues
        .map(
          (cue, i) =>
            `${i + 1}\n${clock(cue.start, ',')} --> ${clock(cue.end, ',')}\n${text(cue)}\n`,
        )
        .join('\n'),
    )
    await writeFile(
      `${output}/ragglass-demo${suffix}.vtt`,
      'WEBVTT\n\n' +
        cues.map((cue) => `${clock(cue.start)} --> ${clock(cue.end)}\n${text(cue)}\n`).join('\n'),
    )
    const assTime = (seconds) => clock(seconds).slice(1, -1)
    const styles = [
      'Style: Title,Noto Sans CJK TC,40,&H009BC6E5,&H009BC6E5,&H00232823,&H00232823,-1,0,0,0,100,100,0,0,1,0,0,8,50,50,0,1',
      'Style: Action,Noto Sans CJK TC,34,&H00F5EEE6,&H00F5EEE6,&H00232823,&H00232823,0,0,0,0,100,100,0,0,1,0,0,8,50,50,0,1',
      'Style: Note,Noto Sans CJK TC,26,&H00B6BBAF,&H00B6BBAF,&H00232823,&H00232823,0,0,0,0,100,100,0,0,1,0,0,8,50,50,0,1',
    ].join('\n')
    const events = cues
      .flatMap((cue) =>
        [
          ['Title', 922, cue.title],
          ['Action', 980, cue.action],
          ['Note', 1032, cue.note],
        ].map(
          ([style, y, value]) =>
            `Dialogue: 0,${assTime(cue.start)},${assTime(cue.end)},${style},,0,0,0,,{\\pos(720,${y})}${value}`,
        ),
      )
      .join('\n')
    await writeFile(
      `${output}/captions${suffix}.ass`,
      `[Script Info]\nScriptType: v4.00+\nPlayResX: 1440\nPlayResY: 1200\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n${styles}\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n${events}\n`,
    )
    execFileSync(
      'ffmpeg',
      [
        '-y',
        '-hide_banner',
        '-loglevel',
        'error',
        '-ss',
        recording.trimmed_initial_navigation_seconds.toFixed(3),
        '-i',
        'live-recording.webm',
        '-t',
        duration.toFixed(3),
        '-vf',
        `pad=iw:ih+300:0:0:color=0x232823,ass=captions${suffix}.ass`,
        '-c:v',
        'libx264',
        '-preset',
        'fast',
        '-crf',
        '23',
        '-pix_fmt',
        'yuv420p',
        '-r',
        '24',
        '-an',
        '-movflags',
        '+faststart',
        '-threads',
        '4',
        `ragglass-demo${suffix}.mp4`,
      ],
      { cwd: output, stdio: 'inherit' },
    )
    const videoBytes = await readFile(`${output}/ragglass-demo${suffix}.mp4`)
    media[language] = {
      filename: `ragglass-demo${suffix}.mp4`,
      ...probeMedia(`ragglass-demo${suffix}.mp4`, output),
      bytes: videoBytes.length,
      sha256: createHash('sha256').update(videoBytes).digest('hex'),
    }
  }
  const clipStart = Math.max(
    0,
    recording.scenes.find((scene) => scene.id === 'citation').start_seconds - 1,
  )
  for (const suffix of ['', '.zh-TW']) {
    execFileSync(
      'ffmpeg',
      [
        '-y',
        '-hide_banner',
        '-loglevel',
        'error',
        '-ss',
        clipStart.toFixed(3),
        '-i',
        `ragglass-demo${suffix}.mp4`,
        '-t',
        '10',
        '-filter_complex',
        '[0:v]fps=8,scale=864:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=3',
        '-loop',
        '0',
        `${images}/demo${suffix}.gif`,
      ],
      { cwd: output, stdio: 'inherit' },
    )
  }
  for (const suffix of ['', '.zh-TW']) {
    for (const extension of ['srt', 'vtt']) {
      const filename = `ragglass-demo${suffix}.${extension}`
      await writeFile(
        new URL(`docs/media/${filename}`, root),
        await readFile(`${output}/${filename}`),
      )
    }
  }
  return media
}

export const mediaRoot = root
export const localMediaDirectory = fileURLToPath(new URL('.data/launch/', root))
