// Mirrors src/amber/api/schemas.py. Every modeled payload carries its verdicts.

export type Nullable<T> = T | null;

export interface DataInfo {
  source: string;
  built_at: Nullable<string>;
  commit: Nullable<string>;
}

export interface Framing {
  project: string;
  scenario: string;
  sd_not_credible: string;
  sc_not_credible: string;
  coverage: string;
  fiscal_year: string;
}

export interface CountryMeta {
  iso3: string;
  name: string;
  treated: boolean;
  donor: boolean;
}

export interface IndicatorMeta {
  id: string;
  name: string;
  pillar: string;
  polarity: string;
  in_index: boolean;
  excluded_reason: Nullable<string>;
  goalpost_low: number;
  goalpost_high: number;
  log_scale: boolean;
}

export interface PillarMeta {
  id: string;
  label: string;
  default_weight: number;
}

export interface LeverMeta {
  name: string;
  label: string;
  description: string;
  min: number;
  max: number;
  step: number;
  default: number;
}

export interface StabilityPoint {
  year: number;
  recovery: number;
}

export interface ScenarioMeta {
  name: string;
  label: string;
  description: string;
  levers: Record<string, number>;
  stability: StabilityPoint[];
  diverges_from: Nullable<number>;
}

export interface OutcomeMeta {
  id: string;
  label: string;
  units: string;
  is_currency: boolean;
}

export interface SeriesMeta {
  id: string;
  label: string;
  kind: "stock" | "indicator" | "pillar" | "combined";
}

export interface Thresholds {
  sc_credible_pre_rmse_share: number;
  sc_placebo_poor_fit_multiple: number;
  sd_credible_nrmse: number;
  sd_sc_tolerance: number;
  sd_profile_tolerance: number;
}

export interface Meta {
  framing: Framing;
  treated_country: string;
  countries: CountryMeta[];
  indicators: IndicatorMeta[];
  pillars: PillarMeta[];
  normalizations: string[];
  default_normalization: string;
  treatment_year: number;
  modeling_window: { start: number; end: number };
  covid_years: number[];
  projection_start: number;
  horizon_end: number;
  levers: LeverMeta[];
  scenarios: ScenarioMeta[];
  baseline_scenario: string;
  counterfactual_scenario: string;
  quantiles: string[];
  ensemble_size: number;
  sc_outcomes: OutcomeMeta[];
  sd_series: SeriesMeta[];
  thresholds: Thresholds;
  historical: HistoricalMeta;
  data: DataInfo;
}

// ---- Historical arc (phase 7) ------------------------------------------ //

export interface HistoricalEvent {
  year: number;
  label: string;
}

/** Observations of `country_iso3` before `standard_from` are low reliability. */
export interface ReliabilityRule {
  country_iso3: string;
  standard_from: number;
}

export interface HistoricalCountryMeta {
  iso3: string;
  name: string;
  role: "treated" | "donor" | "comparator";
}

export interface HistoricalIndicatorMeta {
  id: string;
  name: string;
  /** The ruler: never mixed in one series. */
  source: "wb_constant" | "maddison";
  units: string;
  present: boolean;
}

export interface ComparatorMeta {
  key: string;
  label: string;
  units: string[];
  scenario: string;
  default: boolean;
}

export interface HistoricalFraming {
  divergence: string;
  low_reliability: string;
  modeling_window: string;
  rulers: string;
  maddison: string;
  chained_level: string;
  fiscal_year: string;
  counterfactual_pointer: string;
}

export interface HistoricalMeta {
  window: { start: number; end: number };
  countries: HistoricalCountryMeta[];
  indicators: HistoricalIndicatorMeta[];
  default_indicators: string[];
  default_countries: string[];
  comparators: ComparatorMeta[];
  default_comparator: string;
  divergence_anchor: number;
  sensitivity_anchors: number[];
  events: HistoricalEvent[];
  reliability: ReliabilityRule[];
  framing: HistoricalFraming;
}

export type Reliability = "low" | "standard";

export interface HistoricalRow {
  country_iso3: string;
  indicator_id: string;
  year: number;
  value: Nullable<number>;
  source: "wb_constant" | "maddison";
  reliability: Reliability;
}

export interface HistoricalResponse {
  indicators: string[];
  countries: string[];
  rows: HistoricalRow[];
  events: HistoricalEvent[];
  modeling_window: { start: number; end: number };
  reliability: ReliabilityRule[];
  notes: string[];
}

export interface DivergencePoint {
  year: number;
  actual: Nullable<number>;
  path: Nullable<number>;
  gap: Nullable<number>;
  ratio: Nullable<number>;
  n_units: number;
  reliability: Reliability;
}

export interface DivergenceMetrics {
  anchor_year: number;
  anchor_value: number;
  latest_year: number;
  actual_latest: number;
  path_latest: number;
  gap_latest: number;
  ratio_latest: number;
  actual_growth_pa: number;
  path_growth_pa: number;
  min_units: number;
}

export interface DivergenceSensitivity {
  anchor_year: number;
  anchor_value: number;
  path_latest: number;
  ratio_latest: number;
  default: boolean;
}

/** An illustration, never an estimate: `scenario_illustrative` is always true. */
export interface DivergenceResponse {
  scenario: string;
  comparator: string;
  comparator_label: string;
  anchor_year: number;
  scenario_illustrative: boolean;
  framing: string;
  counterfactual_pointer: string;
  notes: string[];
  series: DivergencePoint[];
  metrics: DivergenceMetrics;
  sensitivity: DivergenceSensitivity[];
}

export interface PanelRow {
  country_iso3: string;
  indicator_id: string;
  year: number;
  value: Nullable<number>;
  imputed: boolean;
}

export interface SeriesCoverage {
  country_iso3: string;
  indicator_id: string;
  last_year_observed: Nullable<number>;
  is_dark: boolean;
}

export interface PanelResponse {
  indicators: string[];
  countries: string[];
  rows: PanelRow[];
  coverage: SeriesCoverage[];
}

export interface IndexRow {
  country_iso3: string;
  country_name: string;
  year: number;
  series: string;
  value: number;
  coverage: number;
}

export interface IndexResponse {
  method: string;
  weights: Record<string, number>;
  computed_live: boolean;
  coverage_note: string;
  rows: IndexRow[];
}

export interface SCCredibility {
  credible: boolean;
  pre_rmse_share: number;
  threshold: number;
  message: Nullable<string>;
}

export interface SCMetrics {
  pre_rmse: number;
  post_rmse: number;
  rmse_ratio: Nullable<number>;
  pre_rmse_share: number;
  pseudo_p_value: number;
  p_value_floor: number;
  rank: number;
  n_units: number;
  n_effective_donors: number;
  n_weighted_donors: number;
  intime_rmse_ratio: Nullable<number>;
  loo_max_deviation: Nullable<number>;
}

export interface SCPoint {
  year: number;
  actual: Nullable<number>;
  synthetic: Nullable<number>;
  gap: Nullable<number>;
}

export interface YearValue {
  year: number;
  value: Nullable<number>;
}

export interface Placebo {
  unit_iso3: string;
  unit_name: string;
  treated: boolean;
  pre_rmse: number;
  poor_fit: boolean;
  gaps: YearValue[];
}

export interface OutcomeResult {
  outcome: string;
  label: string;
  units: string;
  is_currency: boolean;
  credibility: SCCredibility;
  metrics: SCMetrics;
  series: SCPoint[];
  latest: SCPoint;
  latest_gap_share: Nullable<number>;
  weights: { donor_iso3: string; donor_name: string; weight: number }[];
  placebos: Placebo[];
  placebo_time: { placebo_year: number; series: SCPoint[] };
  leave_one_out: { dropped_donor: string; dropped_name: string; synthetic: YearValue[] }[];
  leave_one_out_band: { year: number; low: number; high: number }[];
}

export interface CounterfactualResponse {
  treated_country: string;
  treatment_year: number;
  outcomes: OutcomeResult[];
}

export type Bands = Record<string, Nullable<number>[]>;

export interface SCCheck {
  outcome: string;
  applicable: boolean;
  sc_credible: boolean;
  deviation: Nullable<number>;
  tolerance: number;
  consistent: Nullable<boolean>;
  reason: Nullable<string>;
}

export interface GapSeries {
  quantiles: Bands;
  share_above: Nullable<number>[];
}

export interface ScenarioResult {
  name: string;
  label: string;
  description: string;
  custom: boolean;
  levers: Record<string, number>;
  stability: StabilityPoint[];
  diverges_from: Nullable<number>;
  series: Record<string, Bands>;
  gaps: Nullable<Record<string, GapSeries>>;
  sc_checks: SCCheck[];
}

export interface MetricRow {
  scope: string;
  nrmse: Nullable<number>;
  credible: boolean;
  n_obs: number;
  composition_gap: Nullable<number>;
}

export interface SDCredibility {
  credible: boolean;
  overall_nrmse: number;
  threshold: number;
  message: Nullable<string>;
  framing: string;
  composition_gap: Nullable<number>;
  last_observed_year: number;
  unidentified: string[];
  unidentified_labels: string[];
  profile_flat: boolean;
  metrics: MetricRow[];
}

export interface History {
  years: number[];
  gdp_pc: Nullable<number>[];
  combined: Nullable<number>[];
  combined_coverage: Nullable<number>[];
}

export interface SCOverlay {
  outcome: string;
  credible: boolean;
  years: number[];
  synthetic: Nullable<number>[];
}

export interface ScenariosResponse {
  years: number[];
  projection_start: number;
  quantiles: string[];
  credibility: SDCredibility;
  history: History;
  sc_overlay: SCOverlay[];
  scenarios: ScenarioResult[];
}

export interface SimulateRequest {
  scenario?: string;
  levers?: Record<string, number>;
}

export interface SimulateResponse {
  years: number[];
  projection_start: number;
  quantiles: string[];
  baseline: string;
  credibility: SDCredibility;
  result: ScenarioResult;
}
