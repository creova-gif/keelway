import React from "react";
import { encryptFlagValues } from "flags";
import { FlagValues } from "flags/react";
import { ExperimentExposureReporter } from "./ExperimentExposureReporter";
import type { EvaluatedExperimentMap } from "@/lib/analytics";

interface ExperimentFlagValuesProps {
  values: EvaluatedExperimentMap;
  surface?: string;
}

/**
 * Server Component emitting `<FlagValues />` (encrypted whenever `FLAGS_SECRET`
 * is present, plain in unconfigured local/CI builds) for automatic Vercel Web
 * Analytics & Flags Explorer correlation, plus client funnel exposure registration.
 */
export async function ExperimentFlagValues({
  values,
  surface = "home",
}: ExperimentFlagValuesProps) {
  let serialized: EvaluatedExperimentMap | string = values;
  if (process.env.FLAGS_SECRET) {
    try {
      serialized = await encryptFlagValues(values);
    } catch {
      serialized = values;
    }
  }

  return (
    <>
      <FlagValues values={serialized} />
      <ExperimentExposureReporter values={values} surface={surface} />
    </>
  );
}
