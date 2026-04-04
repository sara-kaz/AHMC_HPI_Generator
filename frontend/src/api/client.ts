import axios, { type AxiosError } from 'axios'
import type { Case, CaseCreate, CaseUpdate, StructuredOutput } from '../types'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({ baseURL: BASE })

/** FastAPI often returns `{ detail: string | object }` — surface that instead of a bare HTTP status. */
export function getApiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const ax = err as AxiosError<{ detail?: unknown }>
    const detail = ax.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const parts = detail.map((item: unknown) =>
        typeof item === 'object' && item !== null && 'msg' in item
          ? String((item as { msg: unknown }).msg)
          : JSON.stringify(item)
      )
      return parts.join('; ')
    }
    if (detail != null) return JSON.stringify(detail)
  }
  if (err instanceof Error) return err.message
  return 'Request failed.'
}

export const casesApi = {
  list: () => api.get<Case[]>('/api/cases').then(r => r.data),

  get: (id: number) => api.get<Case>(`/api/cases/${id}`).then(r => r.data),

  create: (payload: CaseCreate) =>
    api.post<Case>('/api/cases', payload).then(r => r.data),

  generate: (id: number) =>
    api.post<Case>(`/api/cases/${id}/generate`).then(r => r.data),

  clarify: (id: number, answers: string[]) =>
    api.post<Case>(`/api/cases/${id}/clarify`, { answers }).then(r => r.data),

  update: (id: number, payload: CaseUpdate) =>
    api.put<Case>(`/api/cases/${id}`, payload).then(r => r.data),

  delete: (id: number) => api.delete(`/api/cases/${id}`),

  generateAdhoc: (er_note?: string, hp_note?: string) =>
    api.post<StructuredOutput>('/api/generate', { er_note, hp_note }).then(r => r.data),
}
