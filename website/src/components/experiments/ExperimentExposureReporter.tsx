"use client";

import { useEffect } from "react";
import {
  registerEvaluatedExperiments,
  type EvaluatedExperimentMap,
} from "@/lib/analytics";

interface ExperimentExposureReporterProps {
  values: EvaluatedExperimentMap;
  surface?: string;
}

/**
 * Client-side zero-UI bridge that records deduplicated experiment exposures
 * and enriches downstream funnel events (`cta_quickstart_clicked`,
 * `code_snippet_copied`, `early_access_submitted`, etc.) with active A/B variants.
 */
export function ExperimentExposureReporter({
  values,
  surface = "home",
}: ExperimentExposureReporterProps): null {
  useEffect(() => {
    registerEvaluatedExperiments(values, surface);
  }, [values, surface]);

  return null;
}
