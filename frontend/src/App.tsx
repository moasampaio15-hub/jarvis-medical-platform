import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { ApiError, apiRequest } from './lib/api'
import { clearSession, readSession, saveSession } from './lib/session'
import type { DatabaseHealth, TokenResponse, User } from './types'

const modules = [
  { name: 'Pacientes', detail: 'Cadastro e gestão administrativa', accent: 'blue' },
  { name: 'Agenda', detail: 'Consultas e disponibilidade', accent: 'teal' },
  { name: 'Prontuários', detail: 'Histórico assistencial protegido', accent: 'violet' },
  { name: 'Exames', detail: 'Pedidos e resultados laboratoriais', accent: 'amber' },
]

function Brand() {
  return (
    <div className="brand" aria-label="JARVIS Medical">
      <span className="brand-mark" aria-hidden="true">J</span>
      <span><strong>JARVIS</strong><small>Medical Platform</small></span>
    </div>
  )
}

function Login({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokens = await apiRequest<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, senha: password }),
      })
      saveSession(tokens)
      onAuthenticated(await apiRequest<User>('/auth/me'))
    } catch (caught) {
      clearSession()
      setError(caught instanceof ApiError ? caught.message : 'API indisponível. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-layout">
      <section className="login-story">
        <Brand />
        <div className="story-copy">
          <span className="eyebrow">Cuidado conectado</span>
          <h1>Informação clínica organizada para decisões mais seguras.</h1>
          <p>Uma plataforma modular que reúne a operação assistencial com privacidade, rastreabilidade e clareza.</p>
        </div>
        <div className="privacy-note"><span aria-hidden="true">✓</span> Acesso protegido e auditável</div>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <div className="mobile-brand"><Brand /></div>
          <span className="eyebrow">Portal profissional</span>
          <h2>Boas-vindas</h2>
          <p className="muted">Entre com suas credenciais para acessar o ambiente JARVIS.</p>

          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" autoComplete="username" placeholder="nome@instituicao.com.br" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <label htmlFor="password">Senha</label>
          <input id="password" type="password" autoComplete="current-password" placeholder="Sua senha" value={password} onChange={(event) => setPassword(event.target.value)} required />

          {error && <div className="error-message" role="alert">{error}</div>}
          <button className="primary-button" type="submit" disabled={loading}>{loading ? 'Autenticando…' : 'Entrar no portal'}</button>
          <p className="support-copy">Problemas de acesso? Procure o administrador da sua instituição.</p>
        </form>
      </section>
    </main>
  )
}

function Dashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [health, setHealth] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    apiRequest<DatabaseHealth>('/saúde/db').then(() => setHealth('online')).catch(() => setHealth('offline'))
  }, [])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <nav aria-label="Navegação principal">
          <a className="nav-item active" href="#inicio">Visão geral</a>
          {modules.map((module) => <a className="nav-item" href={`#${module.name.toLowerCase()}`} key={module.name}>{module.name}</a>)}
        </nav>
        <button className="logout-button" onClick={onLogout}>Sair com segurança</button>
      </aside>

      <main className="dashboard" id="inicio">
        <header className="topbar">
          <div><span className="eyebrow">Ambiente assistencial</span><h1>Olá, {user.nome.split(' ')[0]}</h1></div>
          <div className={`health-pill ${health}`}><span aria-hidden="true" />{health === 'checking' ? 'Verificando API' : health === 'online' ? 'Sistemas operacionais' : 'API indisponível'}</div>
        </header>

        <section className="welcome-card">
          <div>
            <span className="eyebrow">Sua central de trabalho</span>
            <h2>O essencial da jornada do paciente, em um só lugar.</h2>
            <p>Acesse os módulos conforme as permissões associadas ao seu perfil.</p>
          </div>
          <div className="user-badge"><strong>{user.nome}</strong><span>{user.email}</span></div>
        </section>

        <section aria-labelledby="modules-title">
          <div className="section-heading">
            <div><span className="eyebrow">Módulos</span><h2 id="modules-title">Áreas de trabalho</h2></div>
            <span className="muted">Acesso controlado por RBAC</span>
          </div>
          <div className="module-grid">
            {modules.map((module, index) => (
              <article className={`module-card ${module.accent}`} id={module.name.toLowerCase()} key={module.name}>
                <span className="module-index">0{index + 1}</span><h3>{module.name}</h3><p>{module.detail}</p><button type="button" disabled>Em breve</button>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [restoring, setRestoring] = useState(Boolean(readSession()))
  const logout = useCallback(() => { clearSession(); setUser(null) }, [])

  useEffect(() => {
    if (!readSession()) return
    apiRequest<User>('/auth/me').then(setUser).catch(logout).finally(() => setRestoring(false))
  }, [logout])

  if (restoring) return <div className="loading-screen"><Brand /><span>Restaurando sessão…</span></div>
  return user ? <Dashboard user={user} onLogout={logout} /> : <Login onAuthenticated={setUser} />
}
