import {
  createFlagsDiscoveryEndpoint,
  getProviderData as getLocalProviderData,
} from "flags/next";
import { getProviderData as getVercelProviderData } from "@flags-sdk/vercel";
import * as flags from "../../../../flags";

export const GET = createFlagsDiscoveryEndpoint(async () => {
  try {
    if (process.env.FLAGS || process.env.VERCEL_OIDC_TOKEN) {
      return await getVercelProviderData(flags);
    }
  } catch {
    // Graceful fallback to local code definitions if OIDC credentials are unavailable
  }
  return getLocalProviderData(flags);
});
