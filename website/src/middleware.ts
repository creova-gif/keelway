import { NextResponse, type NextRequest } from "next/server";

export const VISITOR_COOKIE = "kw_vid";
export const OVR_HOME_GATE_COOKIE = "kw_ovr_home_gate";
export const OVR_QUICKSTART_CLI_COOKIE = "kw_ovr_quickstart_cli";

const VALID_HOME_GATE_VARIANTS = new Set([
  "control-stepper",
  "interactive-p10-deck",
]);
const VALID_QUICKSTART_CLI_VARIANTS = new Set([
  "code-tabs-default",
  "interactive-tui-boot",
]);

/**
 * Anonymous sticky A/B bucketing & QA override middleware.
 * - Assigns a zero-PII first-party `kw_vid` UUID cookie if absent so server-side
 *   Vercel Flags (`--by user.id`) and offline fallback splits remain 100% sticky.
 * - Accepts `?kw_home_gate=` and `?kw_quickstart_cli=` query overrides for instant QA.
 */
export function middleware(request: NextRequest): NextResponse {
  const requestHeaders = new Headers(request.headers);

  let visitorId = request.cookies.get(VISITOR_COOKIE)?.value;
  let shouldSetVisitorCookie = false;
  if (!visitorId || visitorId.length < 8) {
    visitorId = crypto.randomUUID();
    shouldSetVisitorCookie = true;
  }
  requestHeaders.set("x-kw-vid", visitorId);

  const url = request.nextUrl;
  const qpHomeGate = url.searchParams.get("kw_home_gate");
  const qpQuickstart = url.searchParams.get("kw_quickstart_cli");

  if (qpHomeGate && VALID_HOME_GATE_VARIANTS.has(qpHomeGate)) {
    requestHeaders.set("x-kw-ovr-home-gate", qpHomeGate);
  }
  if (qpQuickstart && VALID_QUICKSTART_CLI_VARIANTS.has(qpQuickstart)) {
    requestHeaders.set("x-kw-ovr-quickstart-cli", qpQuickstart);
  }

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });

  if (shouldSetVisitorCookie) {
    response.cookies.set(VISITOR_COOKIE, visitorId, {
      path: "/",
      sameSite: "lax",
      httpOnly: false,
      maxAge: 60 * 60 * 24 * 180,
    });
  }

  if (qpHomeGate && VALID_HOME_GATE_VARIANTS.has(qpHomeGate)) {
    response.cookies.set(OVR_HOME_GATE_COOKIE, qpHomeGate, {
      path: "/",
      sameSite: "lax",
      httpOnly: false,
      maxAge: 60 * 60 * 24 * 7,
    });
  } else if (qpHomeGate === "reset") {
    response.cookies.delete(OVR_HOME_GATE_COOKIE);
  }

  if (qpQuickstart && VALID_QUICKSTART_CLI_VARIANTS.has(qpQuickstart)) {
    response.cookies.set(OVR_QUICKSTART_CLI_COOKIE, qpQuickstart, {
      path: "/",
      sameSite: "lax",
      httpOnly: false,
      maxAge: 60 * 60 * 24 * 7,
    });
  } else if (qpQuickstart === "reset") {
    response.cookies.delete(OVR_QUICKSTART_CLI_COOKIE);
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|.well-known|fonts|demos|favicon.svg|og-image.jpg|openapi.json|product-facts.json|install.sh|robots.txt|sitemap.xml).*)",
  ],
};
