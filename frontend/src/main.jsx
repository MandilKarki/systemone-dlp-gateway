import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';

const examples = [
  ['Public release', 'Published product launch copy for Tuesday.', 'public'],
  ['Personal data', 'Customer email: <EMAIL>; account ID: <ID>', 'public'],
  ['Credential', 'API deployment token <TOKEN> for debugging.', 'partner'],
  ['Health data', 'Patient diagnosis and treatment notes.', 'partner']
];

function App() {
  const [provider, setProvider] = useState('jev');
  const [destination, setDestination] = useState('public');
  const [action, setAction] = useState('paste');
  const [evidence, setEvidence] = useState(examples[0][1]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function evaluate() {
    setLoading(true); setError(''); setResult(null);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/evaluate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({provider,destination,action,evidence})});
      if (!response.ok) throw new Error((await response.text()).replace(/<[^>]+>/g, ''));
      setResult(await response.json());
    } catch (e) { setError(`Could not evaluate: ${e.message}. Start python server.py first.`); }
    finally { setLoading(false); }
  }
  return <main>
    <header><div className="eyebrow">SYSTEM ONE · DLP LAB</div><h1>Decide before an agent sends.</h1><p>Test PII classification, egress policy, and triage routing with a typed-decision provider.</p></header>
    <section className="shell">
      <div className="input-card">
        <div className="row title-row"><h2>Transfer under review</h2><span className="status">local test console</span></div>
        <div className="grid">
          <label>Decision lane<select value={provider} onChange={e=>setProvider(e.target.value)}><option value="jev">Jev API</option><option value="laya">Local Laya</option><option value="tamev">Local TAMEV Nano</option><option value="ideanjev">Local IdeaNJEV 4-bit</option></select></label>
          <label>Destination<select value={destination} onChange={e=>setDestination(e.target.value)}><option value="public">Public / external</option><option value="partner">Approved partner</option><option value="internal">Internal</option></select></label>
          <label>Agent action<select value={action} onChange={e=>setAction(e.target.value)}><option value="paste">Paste to tool</option><option value="upload">Upload file</option><option value="send">Send message</option></select></label>
        </div>
        <label className="evidence">Redacted evidence<textarea value={evidence} onChange={e=>setEvidence(e.target.value)} maxLength="8000" /><small>Use redacted excerpts in testing. The browser never receives provider keys.</small></label>
        <div className="examples">{examples.map(([name,text,dest])=><button key={name} onClick={()=>{setEvidence(text);setDestination(dest)}}>{name}</button>)}</div>
        <button className="run" onClick={evaluate} disabled={loading || !evidence.trim()}>{loading ? 'Evaluating…' : 'Evaluate transfer'} <span>→</span></button>
      </div>
      <aside className="result-card">
        <div className="row"><h2>Decision record</h2><span className="dot"></span></div>
        {!result && !error && <div className="empty">Run a transfer test to inspect the bounded decision, PII type, and owning queue.</div>}
        {error && <div className="error">{error}</div>}
        {result && <><div className={`verdict ${result.verdict}`}><span>EGRESS</span><strong>{result.verdict}</strong></div>
          <dl><div><dt>Sensitivity</dt><dd>{result.sensitivity}</dd></div><div><dt>Violation probability</dt><dd>{Math.round(result.probability*100)}%</dd></div><div><dt>PII type</dt><dd>{result.triage.pii_type}</dd></div><div><dt>Triage owner</dt><dd>{result.triage.triage.replace('_',' ')}</dd></div></dl>
          <div className="reason"><b>Policy note</b><p>{result.reason}</p></div></>}
      </aside>
    </section>
    <footer><span>One selected typed-decision model per evaluation.</span><span>Jev and Laya results are benchmarked separately.</span></footer>
  </main>
}
createRoot(document.getElementById('root')).render(<App/>);
