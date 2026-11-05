import { useState } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ---- a controllable fake of the supabase client -------------------------------------------
type Listener = (event: string, session: unknown) => void;
const fake = vi.hoisted(() => ({
  listener: null as null | ((event: string, session: unknown) => void),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("@/lib/supabase", () => ({
  isConfigured: true,
  getAccessToken: async () => "t",
  supabase: {
    auth: {
      onAuthStateChange: (cb: Listener) => {
        fake.listener = cb;
        return { data: { subscription: { unsubscribe: vi.fn() } } };
      },
      signInWithPassword: fake.signInWithPassword,
      signUp: fake.signUp,
      signOut: fake.signOut,
    },
  },
}));

const nav = vi.hoisted(() => ({ pathname: "/workspace", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ replace: nav.replace }),
}));
vi.mock("next/link", () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }));
vi.mock("@/components/layout/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div data-testid="shell">{children}</div> }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, listDocuments: vi.fn(async () => []), getHealth: vi.fn(async () => ({ status: "ok", version: "t", environment: "t", generation_available: false })) };
});

import { AppGate } from "./AppGate";
import { AuthProvider, useAuth } from "./AuthProvider";
import { askQuestion } from "@/lib/api";
import LoginPage from "@/app/login/page";

const session = (id: string, email = `${id}@test.dev`) => ({ user: { id, email } });
const emit = (event: string, s: unknown) => act(() => fake.listener?.(event, s));

function App({ children = <p>PRIVATE CONTENT</p> }: { children?: React.ReactNode }) {
  return (
    <AuthProvider>
      <AppGate>{children}</AppGate>
    </AuthProvider>
  );
}

beforeEach(() => {
  nav.pathname = "/workspace";
  fake.listener = null;
  Object.values(nav).forEach((v) => typeof v === "function" && (v as ReturnType<typeof vi.fn>).mockClear?.());
  fake.signInWithPassword.mockReset();
  fake.signUp.mockReset();
  fake.signOut.mockReset().mockResolvedValue({ error: null });
});

describe("AppGate", () => {
  it("allows the public landing page without requiring a session", async () => {
    nav.pathname = "/";
    render(<App><p>PUBLIC LANDING</p></App>);
    expect(screen.getByText("PUBLIC LANDING")).toBeInTheDocument();
    await emit("INITIAL_SESSION", null);
    expect(screen.getByText("PUBLIC LANDING")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("shows nothing private while the session is still loading", () => {
    render(<App />);
    expect(screen.queryByText("PRIVATE CONTENT")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  it("never renders private pages when signed out, and redirects to /login", async () => {
    render(<App />);
    await emit("INITIAL_SESSION", null);
    expect(screen.queryByText("PRIVATE CONTENT")).toBeNull();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
  });

  it("renders the app for a signed-in user", async () => {
    render(<App />);
    await emit("INITIAL_SESSION", session("u1"));
    expect(await screen.findByText("PRIVATE CONTENT")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("sends a signed-in user away from the login page", async () => {
    nav.pathname = "/login";
    render(<App><p>LOGIN FORM</p></App>);
    await emit("INITIAL_SESSION", session("u1"));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/workspace"));
    expect(screen.queryByText("LOGIN FORM")).toBeNull();
  });

  it("shows the login page to a signed-out visitor", async () => {
    nav.pathname = "/login";
    render(<App><p>LOGIN FORM</p></App>);
    await emit("INITIAL_SESSION", null);
    expect(screen.getByText("LOGIN FORM")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("removes private content immediately on sign-out", async () => {
    render(<App />);
    await emit("INITIAL_SESSION", session("u1"));
    await screen.findByText("PRIVATE CONTENT");
    await emit("SIGNED_OUT", null);
    expect(screen.queryByText("PRIVATE CONTENT")).toBeNull();
  });
});

describe("per-user state is destroyed when the user changes", () => {
  function Counter() {
    const [count, setCount] = useState(0);
    return <button onClick={() => setCount((c) => c + 1)}>count:{count}</button>;
  }

  it("resets all state when a different user signs in", async () => {
    render(<App><Counter /></App>);
    await emit("INITIAL_SESSION", session("alice"));
    await userEvent.click(await screen.findByRole("button", { name: "count:0" }));
    expect(screen.getByRole("button", { name: "count:1" })).toBeInTheDocument();
    await emit("SIGNED_IN", session("bob"));
    expect(await screen.findByRole("button", { name: "count:0" })).toBeInTheDocument();   // fresh state for Bob
  });

  it("keeps state across a token refresh for the same user", async () => {
    render(<App><Counter /></App>);
    await emit("INITIAL_SESSION", session("alice"));
    await userEvent.click(await screen.findByRole("button", { name: "count:0" }));
    await emit("TOKEN_REFRESHED", session("alice"));
    expect(screen.getByRole("button", { name: "count:1" })).toBeInTheDocument();
  });

  it("starts empty again after signing out and back in as the same user", async () => {
    render(<App><Counter /></App>);
    await emit("INITIAL_SESSION", session("alice"));
    await userEvent.click(await screen.findByRole("button", { name: "count:0" }));
    await emit("SIGNED_OUT", null);
    await emit("SIGNED_IN", session("alice"));
    expect(await screen.findByRole("button", { name: "count:0" })).toBeInTheDocument();
  });
});

describe("AuthProvider actions", () => {
  function Probe() {
    const { signIn, signUp, signOut, notice } = useAuth();
    return (
      <div>
        <button onClick={async () => document.body.setAttribute("data-result", String(await signIn("  me@x.dev ", "pw")))}>in</button>
        <button onClick={async () => document.body.setAttribute("data-result", String(await signUp("me@x.dev", "longenough")))}>up</button>
        <button onClick={() => void signOut()}>out</button>
        <p>notice:{notice ?? "none"}</p>
      </div>
    );
  }
  const mountProbe = async () => {
    nav.pathname = "/login";
    render(<AuthProvider><Probe /></AuthProvider>);
    await emit("INITIAL_SESSION", null);
  };
  const result = () => document.body.getAttribute("data-result");

  it("signs in with a trimmed email and reports success as null", async () => {
    fake.signInWithPassword.mockResolvedValue({ error: null });
    await mountProbe();
    await userEvent.click(screen.getByText("in"));
    expect(fake.signInWithPassword).toHaveBeenCalledWith({ email: "me@x.dev", password: "pw" });
    expect(result()).toBe("null");
  });

  it("hides which half of the credentials was wrong", async () => {
    fake.signInWithPassword.mockResolvedValue({ error: { message: "Invalid login credentials: user not found", status: 400 } });
    await mountProbe();
    await userEvent.click(screen.getByText("in"));
    expect(result()).toBe("Incorrect email or password.");
  });

  it("turns rate limits and weak passwords into friendly messages", async () => {
    await mountProbe();
    fake.signInWithPassword.mockResolvedValue({ error: { status: 429, message: "x" } });
    await userEvent.click(screen.getByText("in"));
    expect(result()).toMatch(/Too many attempts/);
    fake.signUp.mockResolvedValue({ data: {}, error: { code: "weak_password", message: "x" } });
    await userEvent.click(screen.getByText("up"));
    expect(result()).toMatch(/stronger password/);
  });

  it("does not reveal whether an email is already registered", async () => {
    fake.signUp.mockResolvedValue({ data: {}, error: { message: "User already registered", status: 422 } });
    await mountProbe();
    await userEvent.click(screen.getByText("up"));
    expect(result()).not.toMatch(/already registered/i);
  });

  it("explains the email-confirmation step when sign-up returns no session", async () => {
    fake.signUp.mockResolvedValue({ data: { session: null }, error: null });
    await mountProbe();
    await userEvent.click(screen.getByText("up"));
    expect(result()).toMatch(/confirm your account/);
  });

  it("signs out of this browser only, not every device", async () => {
    await mountProbe();
    await userEvent.click(screen.getByText("out"));
    expect(fake.signOut).toHaveBeenCalledWith({ scope: "local" });
  });

  it("signs out and explains when the API reports the session is invalid", async () => {
    await mountProbe();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 })));
    // A real API call that comes back 401 must make the provider sign this browser out.
    await act(async () => {
      await askQuestion("anything here", "sources_only", "tfidf").catch(() => {});
    });
    expect(fake.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(screen.getByText("notice:Your session expired. Please sign in again.")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});

describe("LoginPage", () => {
  const mountLogin = async () => {
    nav.pathname = "/login";
    render(<AuthProvider><LoginPage /></AuthProvider>);
    await emit("INITIAL_SESSION", null);
  };

  it("submits with the keyboard and shows a friendly error", async () => {
    fake.signInWithPassword.mockResolvedValue({ error: { message: "bad", status: 400 } });
    await mountLogin();
    await userEvent.type(screen.getByLabelText("Email"), "me@x.dev");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-pass{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
    expect(fake.signInWithPassword).toHaveBeenCalledWith({ email: "me@x.dev", password: "wrong-pass" });
  });

  it("switches to account creation with a minimum password length and the right autocomplete hints", async () => {
    await mountLogin();
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    expect(password).not.toHaveAttribute("minlength");
    await userEvent.click(screen.getByRole("button", { name: "Create an account" }));
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute("minlength", "8");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  });

  it("disables the button while a request is in flight (no double submit)", async () => {
    let finish!: (v: unknown) => void;
    fake.signInWithPassword.mockReturnValue(new Promise((r) => (finish = r)));
    await mountLogin();
    await userEvent.type(screen.getByLabelText("Email"), "me@x.dev");
    await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("button", { name: "Please wait…" })).toBeDisabled();
    await act(async () => finish({ error: null }));
    expect(fake.signInWithPassword).toHaveBeenCalledTimes(1);
  });
});
