// Only the network/time boundary is replaced; client and decoders stay real.
export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

export class FakeClock {
  private time = 0
  now = () => this.time
  advance(ms: number) { this.time += ms }
}

export function transport(...responses: (Response | Error | Promise<Response>)[]) {
  const requests: { url: string; init?: RequestInit }[] = []
  const fetcher: typeof fetch = async (input, init) => {
    requests.push({ url: String(input), init })
    const response = responses.shift()
    if (response instanceof Error) throw response
    if (!response) throw new Error('Unexpected extra request')
    return await response
  }
  return { fetch: fetcher, requests }
}
