import { FormEvent, useEffect, useState } from "react";
import ArchitectureGraph from "./ArchitectureGraph";
import * as api from "./api";
import type { Answer, Architecture, Repository, Session } from "./api";
import { FormattedAnswer } from "./components/FormattedAnswer";

const storedSession = (): Session | null => {
  try {
    const raw = sessionStorage.getItem("repowise-session");
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
};

const storedTheme = (): "light" | "dark" => {
  try {
    const raw = localStorage.getItem("repowise-theme");
    if (raw === "dark" || raw === "light") return raw;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
};

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">(storedTheme);
  const [session, setSession] = useState<Session | null>(storedSession);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selected, setSelected] = useState<Repository | null>(null);
  const [graph, setGraph] = useState<Architecture | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [notice, setNotice] = useState<string>("");
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("repowise-theme", theme);
    } catch {
      // ignore
    }
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  useEffect(() => {
    if (!session) return;
    api
      .repositories(session.accessToken)
      .then((items) => {
        setRepositories(items);
        setSelected((current) => current ?? items[0] ?? null);
      })
      .catch((error: Error) => setNotice(error.message));
  }, [session]);

  const run = async (label: string, action: () => Promise<void>) => {
    setLoading(label);
    setNotice("");
    try {
      await action();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setLoading(null);
    }
  };

  const authenticate = async (
    payload: { name?: string; email: string; password: string },
    mode: "login" | "register",
  ) =>
    run("auth", async () => {
      const next =
        mode === "login"
          ? await api.signIn({ email: payload.email, password: payload.password })
          : await api.signUp({
              name: payload.name!,
              email: payload.email,
              password: payload.password,
            });
      sessionStorage.setItem("repowise-session", JSON.stringify(next));
      setSession(next);
    });

  const signOut = () => {
    sessionStorage.removeItem("repowise-session");
    setSession(null);
    setRepositories([]);
    setSelected(null);
    setGraph(null);
    setAnswer(null);
  };

  if (!session)
    return (
      <AuthScreen
        authenticate={authenticate}
        loading={loading === "auth"}
        notice={notice}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );

  return (
    <main className="shell">
      <header>
        <div className="header-brand">
          <div className="header-brand-logo" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
              <polyline points="2 17 12 22 22 17"></polyline>
              <polyline points="2 12 12 17 22 12"></polyline>
            </svg>
          </div>
          <div>
            <span className="header-brand-name">RepoWise</span>
            <p className="eyebrow" style={{ margin: 0, display: "inline-block" }}>Codebase Architecture & Intelligence</p>
          </div>
        </div>
        <div className="user">
          <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
          <span>{session.user.name}</span>
          <button className="text-button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <section className="intro">
        <div>
          <p className="eyebrow">Architecture Workbench</p>
          <h2>Understand a repository before you change it.</h2>
          <p>
            Index any GitHub repository to map its hierarchical architecture, explore module dependencies, and ask grounded questions in seconds.
          </p>
        </div>
        <AddRepository
          token={session.accessToken}
          onCreated={(repo) => {
            setRepositories((current) => [repo, ...current]);
            setSelected(repo);
            setGraph(null);
            setAnswer(null);
          }}
          run={run}
        />
      </section>

      {notice && (
        <p className="notice" role="alert">
          {notice}
        </p>
      )}

      <section className="workspace">
        <aside>
          <h3>Repositories</h3>
          {repositories.length === 0 ? (
            <p className="empty">Add a public GitHub repository to begin architecture mapping.</p>
          ) : (
            repositories.map((repo) => (
              <button
                key={repo.id}
                className={`repo-card ${selected?.id === repo.id ? "selected" : ""}`}
                onClick={() => {
                  setSelected(repo);
                  setGraph(null);
                  setAnswer(null);
                }}
              >
                <strong>
                  {repo.githubOwner}/{repo.name}
                </strong>
                <span>{repo.primaryLanguage ?? "Repository"}</span>
              </button>
            ))
          )}
        </aside>

        <div className="content">
          {selected ? (
            <RepositoryPanel
              repository={selected}
              token={session.accessToken}
              graph={graph}
              answer={answer}
              setGraph={setGraph}
              setAnswer={setAnswer}
              loading={loading}
              run={run}
            />
          ) : (
            <p className="empty">Select a repository to inspect it.</p>
          )}
        </div>
      </section>
    </main>
  );
}

function AuthScreen({
  authenticate,
  loading,
  notice,
  theme,
  toggleTheme,
}: {
  authenticate: (
    payload: { name?: string; email: string; password: string },
    mode: "login" | "register",
  ) => Promise<void>;
  loading: boolean;
  notice: string;
  theme: "light" | "dark";
  toggleTheme: () => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void authenticate({ name, email, password }, mode);
  };

  return (
    <main className="auth-page">
      <section className="auth-copy">
        <div className="auth-top-bar">
          <div className="auth-brand">
            <div className="auth-brand-logo" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                <polyline points="2 17 12 22 22 17"></polyline>
                <polyline points="2 12 12 17 22 12"></polyline>
              </svg>
            </div>
            <span className="auth-brand-name">RepoWise</span>
          </div>
          <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
        </div>
        <p className="eyebrow">Architecture & Code Intelligence</p>
        <h1>Make an unfamiliar codebase feel familiar.</h1>
        <p>
          Map high-level subsystem architectures, inspect file dependency graphs, and query codebases with grounded AI reasoning.
        </p>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <p className="eyebrow">{mode === "login" ? "Welcome Back" : "Get Started"}</p>
        <h2>{mode === "login" ? "Sign in to RepoWise" : "Create your account"}</h2>
        {mode === "register" && (
          <label>
            Name
            <input
              required
              minLength={2}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ada Lovelace"
            />
          </label>
        )}
        <label>
          Email address
          <input
            required
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="developer@example.com"
          />
        </label>
        <label>
          Password
          <input
            required
            type="password"
            minLength={12}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="12+ characters"
          />
        </label>
        {notice && <p className="notice">{notice}</p>}
        <button disabled={loading}>
          {loading ? "Authenticating…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </form>
    </main>
  );
}

function ThemeToggle({
  theme,
  toggleTheme,
}: {
  theme: "light" | "dark";
  toggleTheme: () => void;
}) {
  return (
    <button
      type="button"
      className="theme-toggle-btn"
      onClick={toggleTheme}
      title={theme === "light" ? "Switch to Dark Mode" : "Switch to Light Mode"}
      aria-label="Toggle dark mode"
    >
      <span>{theme === "light" ? "🌙" : "☀️"}</span>
      <span>{theme === "light" ? "Dark" : "Light"}</span>
    </button>
  );
}

function AddRepository({
  token,
  onCreated,
  run,
}: {
  token: string;
  onCreated: (repository: Repository) => void;
  run: (label: string, action: () => Promise<void>) => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void run("add", async () => {
      const repository = await api.addRepository(token, url);
      onCreated(repository);
      setUrl("");
    });
  };

  return (
    <form className="add-repo" onSubmit={submit}>
      <label>
        Public GitHub Repository URL
        <input
          required
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://github.com/owner/repository"
        />
      </label>
      <button>Add repository</button>
    </form>
  );
}

function RepositoryPanel({
  repository,
  token,
  graph,
  answer,
  setGraph,
  setAnswer,
  loading,
  run,
}: {
  repository: Repository;
  token: string;
  graph: Architecture | null;
  answer: Answer | null;
  setGraph: (graph: Architecture | null) => void;
  setAnswer: (answer: Answer | null) => void;
  loading: string | null;
  run: (label: string, action: () => Promise<void>) => Promise<void>;
}) {
  const [question, setQuestion] = useState("");

  return (
    <>
      <div className="repo-heading">
        <div>
          <p className="eyebrow">{repository.githubOwner}</p>
          <h2>{repository.name}</h2>
          <p>{repository.description ?? "No repository description available."}</p>
        </div>
        <a href={repository.githubUrl} target="_blank" rel="noreferrer">
          Open on GitHub ↗
        </a>
      </div>

      <div className="actions">
        <button
          onClick={() =>
            void run("architecture", async () =>
              setGraph(await api.architecture(token, repository.id)),
            )
          }
          disabled={loading !== null}
        >
          {loading === "architecture" ? "Generating architecture…" : "Generate Architecture"}
        </button>
        <button
          className="secondary"
          onClick={() =>
            void run("index", async () => {
              const result = await api.indexRepository(token, repository.id);
              setAnswer(null);
              window.alert(
                `Indexed ${result.indexed_files} files and ${result.indexed_chunks} code chunks.`,
              );
            })
          }
          disabled={loading !== null}
        >
          {loading === "index" ? "Indexing code…" : "Index for Q&A"}
        </button>
      </div>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">System Architecture</p>
            <h3>Hierarchical Architecture Explorer</h3>
          </div>
          {graph && (
            <span className="badge">
              {graph.statistics
                ? `${graph.statistics.files} files · ${graph.statistics.folders} folders · ${graph.statistics.dependencies} imports`
                : `${graph.nodes.length} nodes`}
            </span>
          )}
        </div>
        {graph ? (
          <ArchitectureGraph graph={graph} />
        ) : (
          <p className="empty">Select “Generate Architecture” to map the hierarchical repository architecture.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Code Q&A Assistant</p>
            <h3>Ask the indexed repository</h3>
          </div>
        </div>

        <div className="qa-suggestions">
          <span className="qa-suggestions-label">Try asking:</span>
          {[
            "How does authentication and authorization work?",
            "Where are database models and schemas defined?",
            "What are the main API endpoints and controllers?",
            "Explain the step-by-step request flow",
          ].map((s) => (
            <button
              key={s}
              type="button"
              className="qa-suggestion-pill"
              onClick={() => setQuestion(s)}
            >
              {s}
            </button>
          ))}
        </div>

        <form
          className="question-form"
          onSubmit={(event) => {
            event.preventDefault();
            void run("question", async () => {
              setAnswer(await api.askQuestion(token, repository.id, question));
            });
          }}
        >
          <input
            required
            minLength={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. How does authentication work or where are database models defined?"
          />
          <button disabled={loading !== null}>
            {loading === "question" ? "Analyzing…" : "Ask Question"}
          </button>
        </form>

        {answer && (
          <div className="answer">
            <div className="answer-header">
              <div className="answer-badge">RepoWise AI Explanation</div>
            </div>
            <FormattedAnswer content={answer.answer} />
            {answer.sources.length > 0 && (
              <div className="answer-sources">
                <p className="eyebrow">Referenced Code Evidence ({answer.sources.length} snippets)</p>
                <ul className="source-list">
                  {answer.sources.map((source) => (
                    <li key={`${source.file_id}-${source.start_line}`} className="source-item">
                      <code className="source-path">{source.file_path}</code>
                      <span className="source-lines">Lines {source.start_line}–{source.end_line}</span>
                      <span className="source-score">{Math.round(source.score * 100)}% match</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>
    </>
  );
}
