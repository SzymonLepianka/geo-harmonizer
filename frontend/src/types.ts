export type Role = 'ADMIN' | 'USER' | 'VIEWER'
export interface User { id: string; email: string; role: Role; is_active: boolean; created_at: string; updated_at: string }
export interface Project { id: string; name: string; description?: string; area_name?: string; created_by_user_id: string; created_at: string; updated_at: string; layer_count: number; analysis_count: number }
export interface Layer { id: string; project_id: string; dataset_import_id: string; name: string; layer_type: string; geometry_type: string; srid: number; attribute_schema: Record<string,string>; style_json?: Record<string,unknown>; is_visible_by_default: boolean; created_at: string; feature_count: number; source_name?: string }
export interface ImportRecord { id: string; status: string; original_filename?: string; detected_format?: string; detected_crs?: string; target_crs: string; feature_count: number; metadata_json: Record<string,unknown>; error_message?: string; log_text?: string; created_at: string }
export interface AnalysisDefinition { id: string; key: string; name: string; description: string; input_requirements: Record<string,string>; parameters_schema: Record<string, number | boolean> }
export interface AnalysisRun { id: string; analysis_key: string; name: string; status: string; input_layer_ids: string[]; parameters_json: Record<string,unknown>; result_summary_json: { result_count?: number; by_type?: Record<string,number>; by_severity?: Record<string,number> }; error_message?: string; created_at: string }
export interface AnalysisResult { id: string; result_type: string; severity: string; label: string; description: string; recommendation: string; metrics_json: Record<string,unknown>; feature_a_id?: string; feature_b_id?: string; created_at: string }
export interface EventLog { id: string; level: string; entity_type: string; message: string; details_json?: Record<string,unknown>; user_id?: string; created_at: string }
export interface RegistrySource { id: string; key: string; name: string; category: string; implementation_status: string; access_mode: string; description: string; limitations?: string; instruction_md?: string }

