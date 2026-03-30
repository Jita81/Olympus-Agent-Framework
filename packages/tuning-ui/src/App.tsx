import { useCallback, useEffect, useState } from 'react'
import './App.css'

const api = (path: string, init?: RequestInit) => fetch(`/api${path}`, init)

type AgentRow = { name: string; current_version_id: string | null }

export default function App() {
  const [agents, setAgents] = useState<AgentRow[]>([])
  const [selectedAgent, setSelectedAgent] = useState('')
  const [prompt, setPrompt] = useState('')
  const [runs, setRuns] = useState<{ run_id: string }[]>([])
  const [selectedRun, setSelectedRun] = useState('')
  const [runDetail, setRunDetail] = useState<unknown>(null)
  const [events, setEvents] = useState<string[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadAgents = useCallback(async () => {
    setError('')
    const r = await api('/agents')
    if (!r.ok) {
      setError(`Agents: ${r.status}`)
      return
    }
    const data = (await r.json()) as AgentRow[]
    setAgents(data)
    if (data.length && !selectedAgent) setSelectedAgent(data[0].name)
  }, [selectedAgent])

  const loadAgentDetail = useCallback(async () => {
    if (!selectedAgent) return
    setError('')
    const r = await api(`/agents/${encodeURIComponent(selectedAgent)}`)
    if (!r.ok) {
      setError(`Agent: ${r.status}`)
      return
    }
    const j = (await r.json()) as { system_prompt: string }
    setPrompt(j.system_prompt)
  }, [selectedAgent])

  const loadRuns = useCallback(async () => {
    setError('')
    const r = await api('/runs?limit=30')
    if (!r.ok) {
      setError(`Runs: ${r.status}`)
      return
    }
    setRuns(await r.json())
  }, [])

  useEffect(() => {
    void loadAgents()
    void loadRuns()
  }, [loadAgents, loadRuns])

  useEffect(() => {
    void loadAgentDetail()
  }, [loadAgentDetail])

  async function savePrompt() {
    setError('')
    setMessage('')
    const r = await api(`/agents/${encodeURIComponent(selectedAgent)}/prompt`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system_prompt: prompt }),
    })
    if (!r.ok) {
      setError(`Save failed: ${r.status}`)
      return
    }
    setMessage('New prompt version saved.')
    void loadAgents()
  }

  async function runDemo() {
    setError('')
    setMessage('')
    const r = await api('/pipelines/demo/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        register_demo: true,
        state: { task: 'Tuning UI' },
      }),
    })
    if (!r.ok) {
      setError(`Run failed: ${r.status}`)
      return
    }
    const j = (await r.json()) as { run_id: string }
    setMessage(`Run ${j.run_id}`)
    setSelectedRun(j.run_id)
    void loadRuns()
    connectLive(j.run_id)
  }

  function connectLive(runId: string) {
    setEvents([])
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${proto}//${host}/ws/runs/${runId}/live`)
    ws.onmessage = (ev) => {
      setEvents((prev) => [...prev.slice(-40), ev.data as string])
    }
    ws.onerror = () => setError('WebSocket error (is olympus-studio running?)')
  }

  async function loadRun() {
    if (!selectedRun) return
    setError('')
    const r = await api(`/runs/${selectedRun}`)
    if (!r.ok) {
      setError(`Run detail: ${r.status}`)
      return
    }
    setRunDetail(await r.json())
    connectLive(selectedRun)
  }

  async function submitFeedback() {
    if (!selectedRun) return
    setError('')
    const r = await api(`/runs/${selectedRun}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        outcome: 'rating_1_5',
        overall_notes: 'from Tuning UI',
        section_feedback: [
          {
            section: 'demo',
            agent: selectedAgent || 'demo-greeter',
            accurate: true,
            complete: true,
            relevant: true,
            notes: '',
          },
        ],
      }),
    })
    if (!r.ok) {
      setError(`Feedback: ${r.status}`)
      return
    }
    setMessage('Feedback recorded.')
  }

  return (
    <div className="app">
      <h1>Olympus Tuning Studio</h1>
      <p style={{ color: '#8b98a5', fontSize: '0.9rem' }}>
        Run <code>olympus-studio</code> from <code>packages/olympus</code>, then{' '}
        <code>npm run dev</code> here. API is proxied via Vite.
      </p>
      {error ? <p className="err">{error}</p> : null}
      {message ? <p className="ok">{message}</p> : null}

      <h2>Agents</h2>
      <div className="panel">
        <div className="row">
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
          >
            {agents.map((a) => (
              <option key={a.name} value={a.name}>
                {a.name}
              </option>
            ))}
          </select>
          <button type="button" className="secondary" onClick={() => void loadAgents()}>
            Refresh
          </button>
        </div>
        <label htmlFor="prompt">System prompt</label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div className="row">
          <button type="button" onClick={() => void savePrompt()}>
            Save prompt (new version)
          </button>
        </div>
      </div>

      <h2>Runs</h2>
      <div className="panel">
        <div className="row">
          <button type="button" className="secondary" onClick={() => void loadRuns()}>
            Refresh runs
          </button>
          <button type="button" onClick={() => void runDemo()}>
            Run demo pipeline
          </button>
        </div>
        <div className="row">
          <select
            value={selectedRun}
            onChange={(e) => setSelectedRun(e.target.value)}
          >
            <option value="">Select run…</option>
            {runs.map((x) => (
              <option key={x.run_id} value={x.run_id}>
                {x.run_id.slice(0, 8)}…
              </option>
            ))}
          </select>
          <button type="button" onClick={() => void loadRun()}>
            Load detail + live
          </button>
          <button type="button" className="secondary" onClick={() => void submitFeedback()}>
            Submit sample feedback
          </button>
        </div>
        {runDetail ? <pre>{JSON.stringify(runDetail, null, 2)}</pre> : null}
        {events.length ? (
          <>
            <h3 style={{ fontSize: '0.85rem', color: '#8b98a5' }}>Live events</h3>
            <div className="events">
              {events.map((e, i) => (
                <div key={i}>{e}</div>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
