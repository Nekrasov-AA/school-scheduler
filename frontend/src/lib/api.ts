import type { GenerateScheduleResponse } from "@/types";

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

export async function generateSchedule(
  files: ScheduleFiles
): Promise<GenerateScheduleResponse> {
  const response = await fetch(`${API_URL}/api/generate-schedule`, {
    method: "POST",
    body: buildFormData(files),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export async function exportSchedule(files: ScheduleFiles): Promise<Blob> {
  const response = await fetch(`${API_URL}/api/generate-schedule/export`, {
    method: "POST",
    body: buildFormData(files),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.blob();
}
