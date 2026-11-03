// goldstack 진행 바 mod의 $.state 계약.
export type ProgressLine = string | null

declare module 'claude-code' {
  interface PluginState {
    goldstack: { line: ProgressLine }
  }
}
