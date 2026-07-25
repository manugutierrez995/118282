export type OptimizationMode = "aesthetic" | "maximum-visibility" | "maximum-clicks" | "maximum-revenue";
export const VALID_MODES: OptimizationMode[] = ["aesthetic","maximum-visibility","maximum-clicks","maximum-revenue"];
export type DeviceTarget = "all" | "desktop" | "mobile";
export type Insertion = "inside" | "before" | "after" | "prepend" | "append" | "replace";
export type CandidateOutcome = "filled" | "no-fill" | "timeout" | "error" | "unknown";
export type ShareBasis = "round-robin" | "weighted-opportunities" | "confirmed-fills";
export type SharePolicy = "protected-share" | "open-yield";
export type OpportunityOutcome = "filled" | "no-fill" | "timeout" | "error" | "collapsed" | "neutral-fallback" | "recovery-fill";
export interface LoaderConfiguration { src?: string; async?: boolean; load_once?: boolean; html?: string; success_message?: string; failure_message?: string; timeout_ms?: number; }
export interface NetworkConfiguration { adapter: string; enabled: boolean; loader?: LoaderConfiguration; allowed_origins?: string[]; }
export interface FormatIdentity { name: string; width: number; height: number; }
export interface AdUnit { network: string; account_id?: string; partner_id?: string; format?: string; markup?: string; head_markup?: string; execute?: string; style?: string; image_url?: string; destination_url?: string; alt_text?: string; html?: string; text?: string; width?: number; height?: number; devices?: DeviceTarget[]; target_blank?: boolean; simulated_outcome?: CandidateOutcome; simulated_delay_ms?: number; external_success_message?: string; external_failure_message?: string; secret_ref?: string; [key: string]: unknown; }
export interface PlacementCandidate { unit: string; priority: number; timeout_ms: number; guaranteed?: boolean; devices?: DeviceTarget[]; }
export interface CandidateResult { outcome: CandidateOutcome; reason?: string; renderedAt?: number; }
export interface PlacementPartner { partner_id: string; partner_name: string; share_target: number; lane: PlacementCandidate[]; }
export interface Placement { id: string; anchor: string; selector?: string; insertion?: Insertion; devices: DeviceTarget[]; priority: number; enabled: boolean; candidates: PlacementCandidate[]; unit?: string; units?: string[]; format?: FormatIdentity; share_basis?: ShareBasis; share_policy?: SharePolicy; partners?: PlacementPartner[]; neutral_fallback?: string; fallback_policy?: "manifest-weighted" | "neutral-fallback" | "collapse"; }
export interface ManifestSettings { enabled: boolean; lazy_load: boolean; collapse_empty_slots: boolean; debug: boolean; allow_unsafe_scripts?: boolean; observe_dom?: boolean; cors_origins?: string[]; }
export interface AdRunnerManifest { spec: "ad-runner/1" | "ad-runner/2"; site: string; version: string; mode: OptimizationMode; settings: ManifestSettings; networks: Record<string, NetworkConfiguration>; units: Record<string, AdUnit>; placements: Placement[]; warnings?: string[]; candidateOrder?: Record<string,string[]>; accounts?: Record<string,{id:string; partner_id:string; network_id:string; loader_network?: string}>; }
export interface BootstrapConfiguration { spec: "ad-runner/1" | "ad-runner/2"; site: string; version: string; manifest: string; publishedAt?: string; }
