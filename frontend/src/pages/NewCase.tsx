import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Sparkles, FileText, ArrowLeft } from 'lucide-react'
import { casesApi } from '../api/client'

const CASE_B_ER = `PHYSICIAN CHART CHIEF COMPLAINT: Diabetes/Hyperglylcemia
HISTORY OF PRESENT ILLNESS: 34 year old female who presents with a chief complaint of Diabetes/Hyperglylcemia. 34 yof hx of T1DM here with AMS in the setting of elevated blood glucose - Insulin dependent - AO2.
PAST MEDICAL HISTORY: History of insulin-dependent diabetes mellitus.
PHYSICAL EXAMINATION: The patient was ill-appearing. The patient was not alert. Tachycardia was present and the rhythm was regular. The patient was oriented to person only.
LABS: BMP: SODIUM 129 (L), CO2 7 (LL), GLU 793 (HH), BUN 43 (H), CREATININE 1.6 (H), GFR 39. CBC: WBC 15.7 (H), HGB 9.1 (L), HCT 28.6 (L). Venous Blood Gas: V pH 7.23 (L), V HCO3 9 (L), V BEvt -17.2 (L). ACETONE: LARGE. LACTIC ACID: 1.7.
IMPRESSION: DKA
DISPOSITION: Admit to ICU. Critical care time 120 minutes.
MDM: Patient presents with DKA supported by significantly elevated anion gap metabolic acidosis, low bicarbonate, lactic acidosis, and hyperglycemia. Requires ICU admission for aggressive management. Insulin drip initiated. IV fluids administered. Empiric antibiotics started.`

const CASE_B_HP = `HISTORY AND PHYSICAL
DATE OF SERVICE: 02/04/2026
CHIEF COMPLAINT: AMS, hyperglycemia
HISTORY OF PRESENT ILLNESS: 34F PMH IDDM, HTN, further history limited by mentation, unclear DM2 versus DM1, taking ASA and lisinopril for unknown reason but presumed HTN, presented via EMS from home for altered mental status. Per ED staff patient has had 3 days nausea and vomiting, weakness, presented for further evaluation. ED labs demonstrated serum glucose of 800, large acetone, ABG with pH of 7.28, bicarb 7, sodium of 129, creatinine of 1.6. Patient admitted for DKA.
PHYSICAL EXAMINATION: General: weak, lethargic, responding to painful stimuli. Lungs: CTAB, mildly tachypneic. CV: mildly tachycardic, regular rhythm. Neuro: reactive to noxious stimuli, not oriented to self, no lateralizing deficits.
ASSESSMENT/PLAN: DKA, pseudohyponatremia, dehydration, AKI, possible gastroenteritis, IDDM. Admit ICU. Insulin GTT. 4L LR bolus. Continue IVF. Replace electrolytes per protocol. Hold lisinopril in setting of AKI.`

export function NewCase() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [erNote, setErNote] = useState('')
  const [hpNote, setHpNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleGenerate() {
    if (!title.trim()) { setError('Please enter a case title.'); return }
    if (!erNote.trim() && !hpNote.trim()) { setError('Please paste at least one clinical note.'); return }
    setError('')
    setLoading(true)
    try {
      const created = await casesApi.create({ title, er_note: erNote || undefined, hp_note: hpNote || undefined })
      const generated = await casesApi.generate(created.id)
      navigate(`/cases/${generated.id}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Generation failed. Check your API key.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  function loadCaseB() {
    setTitle('Case B — 34F T1DM DKA with AMS')
    setErNote(CASE_B_ER)
    setHpNote(CASE_B_HP)
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <button onClick={() => navigate('/')} className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-6 transition-colors">
        <ArrowLeft size={14} /> Back to cases
      </button>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">New Clinical Case</h1>
          <p className="text-sm text-slate-500 mt-1">Paste ER note and/or H&P to generate structured output and Revised HPI</p>
        </div>
        <button
          onClick={loadCaseB}
          className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 text-sm font-medium rounded-xl hover:bg-slate-200 transition-colors"
        >
          <FileText size={14} /> Load Case B
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Case Title <span className="text-red-500">*</span></label>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="e.g. 34F T1DM DKA with AMS"
            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">ER Note</label>
            <textarea
              value={erNote}
              onChange={e => setErNote(e.target.value)}
              placeholder="Paste ER attending note here..."
              rows={14}
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none font-mono"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">H&P Note</label>
            <textarea
              value={hpNote}
              onChange={e => setHpNote(e.target.value)}
              placeholder="Paste H&P note here..."
              rows={14}
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none font-mono"
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>
        )}

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-all text-sm"
        >
          {loading ? (
            <><Loader2 size={16} className="animate-spin" /> Generating with Claude...</>
          ) : (
            <><Sparkles size={16} /> Generate Structured Output + Revised HPI</>
          )}
        </button>
      </div>
    </div>
  )
}
