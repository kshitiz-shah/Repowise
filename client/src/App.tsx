import { FormEvent, useEffect, useState } from "react";
import ArchitectureGraph from "./ArchitectureGraph";
import * as api from "./api";
import type { Answer, Architecture, Repository, Session } from "./api";

const storedSession = (): Session | null => {
  try {
    const raw = sessionStorage.getItem("repowise-session");
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
};

export default function App() {
  const [session, setSession] = useState<Session | null>(storedSession);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selected, setSelected] = useState<Repository | null>(null);
  const [graph, setGraph] = useState<Architecture | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [notice, setNotice] = useState<string>("");
  const [loading, setLoading] = useState<string | null>(null);

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
      />
    );

  return (
    <main className="shell">
      <header>
        <div>
          <p className="eyebrow">REPOSITORY INTELLIGENCE</p>
          <h1>RepoWise</h1>
        </div>
        <div className="user">
          <span>{session.user.name}</span>
          <button className="text-button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <section className="intro">
        <div>
          <p className="eyebrow">YOUR WORKSPACE</p>
          <h2>Understand a repository before you change it.</h2>
          <p>
            Add a public GitHub URL, explore its hierarchical architecture, then ask questions grounded in its code.
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
            <p className="empty">Add a public GitHub repository to begin.</p>
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
}: {
  authenticate: (
    payload: { name?: string; email: string; password: string },
    mode: "login" | "register",
  ) => Promise<void>;
  loading: boolean;
  notice: string;
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
        <p className="eyebrow">REPOWISE / B.TECH PROJECT</p>
        <h1>Make an unfamiliar codebase feel familiar.</h1>
        <p>Map the architecture, retrieve relevant code, and explore how the pieces connect.</p>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <p className="eyebrow">{mode === "login" ? "WELCOME BACK" : "CREATE ACCOUNT"}</p>
        <h2>{mode === "login" ? "Sign in" : "Start exploring"}</h2>
        {mode === "register" && (
          <label>
            Name
            <input
              required
              minLength={2}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
        )}
        <label>
          Email
          <input
            required
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
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
          {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
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
        Public GitHub repository URL
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
          {loading === "architecture" ? "Building architecture…" : "Build architecture"}
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
            <p className="eyebrow">SYSTEM ARCHITECTURE</p>
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
          <p className="empty">Select “Build architecture” to explore the hierarchical repository architecture.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">CODE Q&A</p>
            <h3>Ask the indexed repository</h3>
          </div>
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
            placeholder="How does authentication work?"
          />
          <button disabled={loading !== null}>
            {loading === "question" ? "Thinking…" : "Ask"}
          </button>
        </form>
        {answer && (
          <div className="answer">
            <p>{answer.answer}</p>
            {answer.sources.length > 0 && (
              <div>
                <p className="eyebrow">SOURCES</p>
                <ul>
                  {answer.sources.map((source) => (
                    <li key={`${source.file_id}-${source.start_line}`}>
                      <code>
                        {source.file_path}:{source.start_line}–{source.end_line}
                      </code>
                      <span>{Math.round(source.score * 100)}% match</span>
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
