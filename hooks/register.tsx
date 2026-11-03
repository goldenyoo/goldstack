// goldstack 진행 바: `gs go`가 도는 동안 프롬프트 위(AbovePrompt)에 state.json의 progress.line을 그린다.
// 계산은 gs가 한다(state.py calculate_progress). 이 mod는 고르고 그리기만 한다.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { ProgressLine } from '../types'

const WORK = '.goldstack/work'
const FRESH_MS = 10 * 60 * 1000

const line = atom({ plugin: 'goldstack', key: 'line' } as const, null as ProgressLine)

// `.goldstack/work/*/run/state.json` 중 finished_at이 비었고 최근 10분 안에 바뀐 것 하나(가장 최근)의 progress.line.
// 고를 것이 없거나 읽지 못하면 null. 가장 최근 파일을 읽지 못하면 더 오래된 실행으로 넘어가지 않는다
// (다른 실행의 진행을 지금 것처럼 보이지 않게).
const pick = async ($: EngineInterface): Promise<ProgressLine> => {
  // 없는 경로는 exists로 먼저 거른다(list·stat의 ENOENT가 1초마다 debug 로그에 쌓이지 않게).
  if (!(await $.fs.exists(WORK))) return null
  const now = await $.clock.now()
  const candidates: { path: string; mtimeMs: number }[] = []
  for (const f of await $.fs.list(WORK)) {
    if (f.kind !== 'dir') continue
    const path = `${WORK}/${f.name}/run/state.json`
    if (!(await $.fs.exists(path))) continue
    const st = await $.fs.stat(path)
    if (st.kind === 'file' && now - st.mtimeMs <= FRESH_MS) {
      candidates.push({ path, mtimeMs: st.mtimeMs })
    }
  }
  candidates.sort((a, b) => b.mtimeMs - a.mtimeMs)
  for (const c of candidates) {
    try {
      const data = JSON.parse((await $.fs.read(c.path)) as string)
      if (data?.finished_at) continue
      const text = data?.progress?.line
      return typeof text === 'string' && text !== '' ? text : null
    } catch {
      return null
    }
  }
  return null
}

const refresh = async ($: EngineInterface) => {
  const next = await pick($).catch(() => null)
  if ((await read($, line)) !== next) {
    await update($, line, () => next)
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await refresh($)
    $.clock.every(1000, () => {
      void refresh($)
    })
    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const text = await read($, line)
    if (e.props.hasSurvey || text === null) {
      return next(e)
    }
    const { Text } = $.ui.resolve(e)
    return <Text dimColor wrap="truncate-end">{text}</Text>
  })
}
