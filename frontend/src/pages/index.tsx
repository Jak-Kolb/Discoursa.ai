import { useRouter } from 'next/router';
import { useState } from 'react';
import { useSession, signIn, signOut } from 'next-auth/react';
import { Settings, LogOut } from 'lucide-react';

import { getSubtopics, uploadDocument } from '../lib/api';

export default function HomePage() { // landing page for topic selection
  const { data: session } = useSession();
  const router = useRouter();
  const [step, setStep] = useState<'topic' | 'setup'>('topic');
  const [topic, setTopic] = useState('');
  const [subtopics, setSubtopics] = useState<string[]>([]);
  const [articleText, setArticleText] = useState('');
  const [uploadCount, setUploadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [apiKey, setApiKey] = useState('');

  const handleSaveKey = async () => {
    if (!session?.user?.id) return;
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/user/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          twitter_id: (session as any).user.id, // Type assertion for now
          openai_api_key: apiKey
        })
      });
      setShowSettings(false);
      alert('API Key saved!');
    } catch (e) {
      console.error(e);
      alert('Failed to save key');
    }
  };

  const handleGetSubtopics = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const subs = await getSubtopics(topic);
      setSubtopics(subs);
      setStep('setup');
    } catch (err) {
      setError('Failed to generate subtopics. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!articleText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await uploadDocument(articleText);
      setUploadCount((c) => c + 1);
      setArticleText('');
    } catch (err) {
      setError('Failed to upload article.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleStartDebate = () => {
    router.push({ pathname: '/debate', query: { topic } });
  };

  return (
    <main className="app-shell">
      <section className="panel home-panel">
        <header style={{ textAlign: 'center', marginBottom: '2rem', position: 'relative' }}>
          <div style={{ position: 'absolute', right: 0, top: 0, display: 'flex', gap: '10px' }}>
            {!session ? (
              <button 
                className="button button-secondary"
                onClick={() => signIn('twitter')}
              >
                Connect Twitter
              </button>
            ) : (
              <>
                <button 
                  className="button button-icon"
                  onClick={() => setShowSettings(true)}
                  title="Settings"
                >
                  <Settings size={20} />
                </button>
                <button 
                  className="button button-icon"
                  onClick={() => signOut()}
                  title="Sign Out"
                >
                  <LogOut size={20} />
                </button>
              </>
            )}
          </div>
          <p className="eyebrow">AI Debate Partner</p>
          <h1 style={{ margin: 0, fontSize: '2.5rem' }}>Sharpen your arguments</h1>
          <p className="helper-text" style={{ marginTop: '0.5rem' }}>
            Generate subtopics, gather evidence, and challenge an opposition stance.
          </p>
        </header>

        {error && <p className="alert alert--error" role="status">{error}</p>}

        {step === 'topic' && (
          <div className="form-grid">
            <div className="form-grid">
              <label htmlFor="topic-entry" className="helper-text">
                What topic do you want to debate?
              </label>
              <input
                id="topic-entry"
                className="input-field"
                placeholder="e.g., Universal Basic Income"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGetSubtopics()}
              />
            </div>
            <button
              className="button button-primary button-full"
              onClick={handleGetSubtopics}
              disabled={loading || !topic.trim()}
              type="button"
            >
              {loading ? 'Generating subtopics…' : 'Next'}
            </button>
          </div>
        )}

        {step === 'setup' && (
          <div className="form-grid">
            <div>
              <h3 style={{ marginTop: 0 }}>Suggested subtopics</h3>
              <p className="helper-text" style={{ marginBottom: '0.75rem' }}>
                Use these prompts to stress-test your position.
              </p>
              <ul className="chip-list">
                {subtopics.map((sub, i) => (
                  <li key={i} className="chip">
                    {sub}
                  </li>
                ))}
              </ul>
            </div>

            <div className="surface-subtle form-grid">
              <div>
                <h3 style={{ margin: 0 }}>Upload evidence (optional)</h3>
                <p className="helper-text">
                  Paste relevant article text to add it to the shared context.
                </p>
              </div>
              <textarea
                className="textarea-field"
                placeholder="Paste article content here..."
                value={articleText}
                onChange={(e) => setArticleText(e.target.value)}
              />
              <div className="action-row">
                <span className="helper-text">
                  {uploadCount} article{uploadCount !== 1 ? 's' : ''} uploaded
                </span>
                <button
                  className="button button-secondary"
                  onClick={handleUpload}
                  disabled={loading || !articleText.trim()}
                  type="button"
                >
                  {loading ? 'Uploading…' : 'Upload article'}
                </button>
              </div>
            </div>

            <button className="button button-primary button-full" onClick={handleStartDebate} type="button">
              Start debate
            </button>
          </div>
        )}

        {showSettings && (
          <div className="modal-overlay">
            <div className="modal-content panel">
              <h3>Settings</h3>
              <p>Enter your OpenAI API Key to enable the Twitter bot.</p>
              <input 
                type="password" 
                className="input-field"
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <div style={{ display: 'flex', gap: '10px', marginTop: '1rem' }}>
                <button className="button button-primary" onClick={handleSaveKey}>Save</button>
                <button className="button button-secondary" onClick={() => setShowSettings(false)}>Cancel</button>
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
