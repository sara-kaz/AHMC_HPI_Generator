export type DispositionRecommendation = 'Admit' | 'Observe' | 'Discharge' | 'Unknown'
export type GenerationStatus = 'pending' | 'generating' | 'completed' | 'failed'

export interface StructuredOutput {
  chief_complaint: string
  hpi_summary: string
  key_findings: string[]
  suspected_conditions: string[]
  disposition_recommendation: DispositionRecommendation
  admission_criteria_met: string[]
  uncertainties: string[]
  revised_hpi: string
}

export interface Case {
  id: number
  title: string
  er_note: string | null
  hp_note: string | null
  structured_output: StructuredOutput | null
  edited_fields: string[]
  generation_status: GenerationStatus
  generation_error: string | null
  created_at: string
  updated_at: string
}

export interface CaseCreate {
  title: string
  er_note?: string
  hp_note?: string
  /** Omit or leave unset for database auto-increment. Must be unique. */
  id?: number
}

export interface CaseUpdate {
  title?: string
  structured_output?: StructuredOutput
  edited_fields?: string[]
}
