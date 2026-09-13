export interface ScheduleSlot {
  day: string;
  period: number;
  teacher_id: string;
  class_name: string;
  subject: string;
  group?: string | null;
  room?: string | null;
}

export interface ValidationIssue {
  severity: "error" | "warning";
  message: string;
  context: Record<string, unknown>;
}

export interface GenerateScheduleResponse {
  schedule: ScheduleSlot[];
  solver_status: "optimal" | "feasible" | "infeasible" | "timeout" | string;
  warnings: ValidationIssue[];
}

export interface JobCreatedResponse {
  job_id: string;
  status: "pending";
}

export interface JobStatusResponse {
  job_id: string;
  status: "pending" | "done" | "error";
  result: GenerateScheduleResponse | null;
  error: string | null;
}
