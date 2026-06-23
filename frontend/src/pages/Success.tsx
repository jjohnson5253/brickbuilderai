import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { CheckCircle2, Package } from "lucide-react";
import { SEO } from "../components/SEO";
import { SiteFooter } from "../components/SiteFooter";

type Session = {
  id: string;
  customer_details?: { email?: string };
  amount_total?: number; // cents
  currency?: string;     // "usd"
};

export default function Success() {
  const [params] = useSearchParams();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const sessionId = params.get("session_id");
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        if (!sessionId) return;
        const res = await fetch(`/api/checkout-session?session_id=${sessionId}`);
        const json = await res.json();
        setSession(json);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-[#fbfbfd]">
      <SEO title="Order Confirmed — BrickBuilder" description="Your brick kit order has been placed successfully." url="https://brickbuilder.ai/success" noIndex />
      {/* Header with logo */}
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <img
              src="/logo.svg"
              alt="BrickBuilder"
              className="h-7 w-auto"
              onError={(e) => {
                const el = e.currentTarget as HTMLImageElement;
                el.style.display = "none";
              }}
            />
            <span className="text-xl font-extrabold tracking-tight">
              <span className="text-[#f44336]">BRICK</span>
              <span className="text-slate-900">BUILDER</span>
            </span>
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-2xl px-4 sm:px-6 py-12 sm:py-16">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
            <CheckCircle2 className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-3">
            Thank you for your order! 🎉
          </h1>
          <p className="text-lg text-slate-600">
            We've sent a confirmation email{session?.customer_details?.email ? ` to ${session.customer_details.email}` : ""}.
          </p>
        </div>

        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
            <div className="inline-block w-8 h-8 border-4 border-slate-200 border-t-[#f44336] rounded-full animate-spin mb-3"></div>
            <p className="text-slate-600">Loading order details…</p>
          </div>
        ) : session ? (
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="bg-[#f44336] px-6 py-4 flex items-center gap-3">
              <Package className="w-6 h-6 text-white" />
              <h2 className="text-lg font-semibold text-white">Order Details</h2>
            </div>
            <div className="p-6 space-y-4">
              <div className="flex justify-between items-center pb-4 border-b border-slate-200">
                <span className="text-sm text-slate-600">Order ID</span>
                <span className="font-mono text-sm font-medium text-slate-900">{session.id}</span>
              </div>
              {typeof session.amount_total === "number" && (
                <div className="flex justify-between items-center pb-4 border-b border-slate-200">
                  <span className="text-sm text-slate-600">Total Paid</span>
                  <span className="text-xl font-bold text-slate-900">
                    {(session.amount_total / 100).toLocaleString(undefined, {
                      style: "currency",
                      currency: session.currency?.toUpperCase() || "USD",
                    })}
                  </span>
                </div>
              )}
              <div className="bg-slate-50 rounded-lg p-4">
                <p className="text-sm text-slate-600 text-center">
                  📦 You'll receive tracking information when your kit ships.
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <div className="mt-8 text-center">
          <button
            onClick={() => navigate("/dashboard")}
            className="inline-flex items-center gap-2 bg-[#f44336] text-white rounded-full px-6 py-3 text-base font-medium cursor-pointer transition-all duration-200 hover:bg-[#ff6b6b] hover:-translate-y-0.5 hover:shadow-lg border-none"
          >
            Go to Dashboard
          </button>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
