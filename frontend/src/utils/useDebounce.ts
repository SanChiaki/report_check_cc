
/**
 * Creates a debounced version of a function.
 * @param fn - Function to debounce
 * @param delayMs - Delay in milliseconds
 * @returns Debounced function with a cancel method
 */
export function useDebounceFn<T extends (...args: any[]) => any>(
  fn: T,
  delayMs: number,
): T & { cancel: () => void } {
  let timer: ReturnType<typeof setTimeout> | null = null

  const debounced = ((...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn(...args)
      timer = null
    }, delayMs)
  }) as T & { cancel: () => void }

  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return debounced
}
