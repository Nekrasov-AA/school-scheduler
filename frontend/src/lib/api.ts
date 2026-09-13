import type { JobCreatedResponse, JobStatusResponse } from "@/types";

export interface ScheduleFiles {
  upNoo: File;
  upOoo: File;
  upSoo: File;
  workload: File;
}

const API_URL = import.meta.env.VITE_API_URL || "";

function buildFormData(files: ScheduleFiles): FormData {
  const formData = new FormData();
  formData.append("up_noo", files.upNoo);
  formData.append("up_ooo", files.upOoo);
  formData.append("up_soo", files.upSoo);
  formData.append("workload", files.workload);
  return formData;
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
  } catch {
    // response body wasn't JSON; fall through to generic message
  }
  return `Ошибка сервера (код ${response.status})`;
}

// Schedule generation runs as a background job on the server (a CP-SAT solve
// can take minutes), so this only submits the files and returns a job_id -
// use getJobStatus to poll for the result.
export async function submitScheduleJob(files: ScheduleFiles): Promise<string> {
  const response = await fetch(`${API_URL}/api/generate-schedule`, {
    method: "POST",
    body: buildFormData(files),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  const data: JobCreatedResponse = await response.json();
  return data.job_id;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${API_URL}/api/jobs/${jobId}`);

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export async function exportJobResult(jobId: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/api/jobs/${jobId}/export`);

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.blob();
}
