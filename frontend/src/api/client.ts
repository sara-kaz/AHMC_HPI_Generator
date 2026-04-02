import axios from 'axios'
import type { Case, CaseCreate, CaseUpdate, StructuredOutput } from '../types'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({ baseURL: BASE })

export const casesApi = {
  list: () => api.get<Case[]>('/api/cases').then(r => r.data),

  get: (id: number) => api.get<Case>(`/api/cases/${id}`).then(r => r.data),

  create: (payload: CaseCreate) =>
    api.post<Case>('/api/cases', payload).then(r => r.data),

  generate: (id: number) =>
    api.post<Case>(`/api/cases/${id}/generate`).then(r => r.data),

  update: (id: number, payload: CaseUpdate) =>
    api.put<Case>(`/api/cases/${id}`, payload).then(r => r.data),

  delete: (id: number) => api.delete(`/api/cases/${id}`),

  generateAdhoc: (er_note?: string, hp_note?: string) =>
    api.post<StructuredOutput>('/api/generate', { er_note, hp_note }).then(r => r.data),
}
