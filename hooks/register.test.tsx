// `claude plugin test .`: 진행 바가 progress가 있을 때 그리고, 없을 때 아무것도 그리지 않는지.
import { expect, mock, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'
import type { On } from 'claude-code'

type Engine = Parameters<TestBody>[0]

const NOW = Date.parse('2026-11-03T12:00:00Z')
const MIN = 60 * 1000

const BAND = {
  plugin: 'goldstack',
  component: 'AbovePrompt',
  requestId: 'band',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 80,
    scroll: { offset: 0, bodyRows: 10 },
    view: {},
  },
} as const

type Run = { mtimeMs: number; state: unknown }

// 가짜 레포: `.goldstack/work/<feature>/run/state.json`. state가 문자열이면 그대로(깨진 JSON) 준다.
// $.fs는 상대 경로를 작업 디렉터리 기준 절대 경로로 바꿔 넘기므로 끝부분으로 맞춘다.
const WORK = /(?:^|\/)\.goldstack\/work$/
const STATE = /(?:^|\/)\.goldstack\/work\/([^/]+)\/run\/state\.json$/

const repo = (on: On, runs: Record<string, Run>) => {
  const runOf = (path: string) => {
    const m = STATE.exec(path)
    return m ? runs[m[1]!] : undefined
  }
  on('fs.exists', (_, e) => ({ value: WORK.test(e.path) ? Object.keys(runs).length > 0 : runOf(e.path) !== undefined }))
  on('fs.list', (_, e) => {
    if (!WORK.test(e.path)) return { deny: 'ENOENT' }
    return { value: Object.keys(runs).map(name => ({ name, kind: 'dir', size: 0, mtimeMs: 0, isLink: false })) }
  })
  on('fs.stat', (_, e) => {
    const run = runOf(e.path)
    if (!run) return { deny: 'ENOENT' }
    return { value: { kind: 'file', size: 1, mtimeMs: run.mtimeMs, isLink: false } }
  })
  on('fs.read', (_, e) => {
    const run = runOf(e.path)
    if (!run) return { deny: 'ENOENT' }
    return { value: typeof run.state === 'string' ? run.state : JSON.stringify(run.state) }
  })
}

// 엔진 자리: mod가 next(e)로 넘기면 이 줄이 보인다(실제 엔진은 AbovePrompt에 아무것도 그리지 않는다).
const ENGINE = '(engine)'

const start = async ($: Engine, on: On) => {
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{ENGINE}</Text>
  })
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
}

// mod가 그린 줄들. mod가 넘기면 엔진 자리 줄만 보이므로 빈 배열이 된다.
const shown = async ($: Engine) => {
  const texts: string[] = []
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    const all = (await ui.findAll({ type: 'Text' })).map(t => t.text)
    expect(all.length).toBe(1)
    texts.push(...all.filter(t => t !== ENGINE))
    await ui.unmount()
  }
  return texts
}

const LIVE = (line: string) => ({ finished_at: '', progress: { line } })

test('progress가 있으면 그 줄을 그린다', async ($, on) => {
  mock.clock(on, { now: NOW })
  repo(on, { 'goldstack-v2': { mtimeMs: NOW - 5000, state: LIVE('3/8 · 04 review · ETA 12분') } })
  await start($, on)

  expect(await shown($)).toEqual(['3/8 · 04 review · ETA 12분', '3/8 · 04 review · ETA 12분'])
})

test('progress가 없으면 아무것도 그리지 않는다', async ($, on) => {
  mock.clock(on, { now: NOW })
  repo(on, {})
  await start($, on)

  expect(await shown($)).toEqual([])
})

test('끝난 실행, 10분 넘게 안 바뀐 실행, 깨진 파일, 빈 line은 그리지 않는다', async ($, on) => {
  mock.clock(on, { now: NOW })
  repo(on, {
    done: { mtimeMs: NOW - 1000, state: { finished_at: '2026-11-03T20:59:59+09:00', progress: { line: 'done' } } },
    stale: { mtimeMs: NOW - 11 * MIN, state: LIVE('stale') },
    broken: { mtimeMs: NOW - 2000, state: '{"finished_at": ' },
    empty: { mtimeMs: NOW - 3000, state: { finished_at: '' } },
  })
  await start($, on)

  expect(await shown($)).toEqual([])
})

test('살아 있는 실행 여럿이면 가장 최근에 바뀐 것을 그린다', async ($, on) => {
  mock.clock(on, { now: NOW })
  repo(on, {
    older: { mtimeMs: NOW - 4 * MIN, state: LIVE('older') },
    newer: { mtimeMs: NOW - 1 * MIN, state: LIVE('newer') },
  })
  await start($, on)

  expect(await shown($)).toEqual(['newer', 'newer'])
})

test('1초마다 다시 읽어 바뀐 줄을 그리고, 실행이 끝나면 지운다', async ($, on) => {
  const clock = mock.clock(on, { now: NOW })
  const runs: Record<string, Run> = { f: { mtimeMs: NOW, state: LIVE('1/2') } }
  repo(on, runs)
  await start($, on)
  expect(await shown($)).toEqual(['1/2', '1/2'])

  runs.f = { mtimeMs: NOW + 1000, state: LIVE('2/2') }
  await clock.advance(1000)
  expect(await shown($)).toEqual(['2/2', '2/2'])

  runs.f = { mtimeMs: NOW + 2000, state: { finished_at: '2026-11-03T21:00:02+09:00', progress: { line: '2/2' } } }
  await clock.advance(1000)
  expect(await shown($)).toEqual([])
})
