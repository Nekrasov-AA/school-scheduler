import React, { useEffect, useRef, useState } from "react";
import {
  Calendar,
  ChevronDown,
  ChevronUp,
  Download,
  Loader2,
  XCircle,
} from "lucide-react";
import { ScheduleForm } from "@/components/ScheduleForm";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { exportJobResult, getJobStatus, submitScheduleJob, type ScheduleFiles } from "@/lib/api";
import type { GenerateScheduleResponse } from "@/types";

const WARNINGS_COLLAPSE_THRESHOLD = 5;
const JOB_POLL_INTERVAL_MS = 2000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const SOLVER_STATUS_LABEL: Record<string, string> = {
  optimal: "Оптимальное решение",
  feasible: "Допустимое решение",
  infeasible: "Решение не найдено",
  timeout: "Превышено время ожидания",
};

const SOLVER_FAILURE_MESSAGE: Record<string, string> = {
  infeasible:
    "Не удалось построить расписание: при текущих учебных планах и нагрузке задача не имеет допустимого решения. Проверьте входные файлы на противоречия.",
  timeout:
    "Решатель не успел найти решение за отведённое время. Попробуйте повторить запрос позже или упростить исходные данные.",
};

function solverBadgeVariant(status: string): "success" | "warning" | "destructive" {
  if (status === "optimal") return "success";
  if (status === "feasible") return "warning";
  return "destructive";
}

export const App: React.FC = () => {
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [result, setResult] = useState<GenerateScheduleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warningsCollapsed, setWarningsCollapsed] = useState(false);

  // Guards against a stale poll loop applying results after a newer
  // submission has started (the form itself prevents concurrent submits via
  // isGenerating, but this keeps polling safe regardless).
  const activeJobRef = useRef<string | null>(null);

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || "";
    fetch(`${apiUrl}/api/health`)
      .then((res) => setBackendOnline(res.ok))
      .catch(() => setBackendOnline(false));
  }, []);

  const handleSubmit = async (files: ScheduleFiles) => {
    setIsGenerating(true);
    setError(null);
    setResult(null);
    setJobId(null);

    try {
      const newJobId = await submitScheduleJob(files);
      activeJobRef.current = newJobId;
      setJobId(newJobId);

      // Schedule generation runs as a background job on the server (a
      // CP-SAT solve can take minutes on constrained hosts), so we poll for
      // the result instead of waiting on a single long request.
      while (activeJobRef.current === newJobId) {
        const statusResponse = await getJobStatus(newJobId);

        if (statusResponse.status === "done" && statusResponse.result) {
          setResult(statusResponse.result);
          setWarningsCollapsed(statusResponse.result.warnings.length > WARNINGS_COLLAPSE_THRESHOLD);
          break;
        }

        if (statusResponse.status === "error") {
          setError(statusResponse.error ?? "Не удалось сгенерировать расписание.");
          break;
        }

        await sleep(JOB_POLL_INTERVAL_MS);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сгенерировать расписание.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!jobId) return;

    setIsDownloading(true);
    setError(null);

    try {
      const blob = await exportJobResult(jobId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "schedule.docx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось скачать файл расписания.");
    } finally {
      setIsDownloading(false);
    }
  };

  const isSuccess = result && result.solver_status !== "infeasible" && result.solver_status !== "timeout";
  const failureMessage = result ? SOLVER_FAILURE_MESSAGE[result.solver_status] : null;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-white">
        <div className="container flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-blue-50 p-2 text-blue-600">
              <Calendar className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">School Scheduler</h1>
              <p className="text-sm text-muted-foreground">
                Автоматическое составление школьного расписания
              </p>
            </div>
          </div>
          {backendOnline !== null && (
            <Badge variant={backendOnline ? "success" : "destructive"}>
              {backendOnline ? "Бэкенд активен" : "Бэкенд недоступен"}
            </Badge>
          )}
        </div>
      </header>

      <main className="container max-w-3xl space-y-6 py-8">
        <ScheduleForm isLoading={isGenerating} onSubmit={handleSubmit} />

        {error && (
          <Alert variant="destructive">
            <XCircle className="h-4 w-4" />
            <AlertTitle>Ошибка</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {result && (
          <Card className="shadow-md">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Результат генерации</CardTitle>
                <Badge variant={solverBadgeVariant(result.solver_status)}>
                  {SOLVER_STATUS_LABEL[result.solver_status] ?? result.solver_status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {failureMessage && (
                <Alert variant="destructive">
                  <XCircle className="h-4 w-4" />
                  <AlertTitle>Расписание не построено</AlertTitle>
                  <AlertDescription>{failureMessage}</AlertDescription>
                </Alert>
              )}

              {result.warnings.length > 0 && (
                <Alert>
                  <div className="flex items-center justify-between gap-2">
                    <AlertTitle className="mb-0">
                      Предупреждения ({result.warnings.length})
                    </AlertTitle>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setWarningsCollapsed((prev) => !prev)}
                    >
                      {warningsCollapsed ? (
                        <>
                          Показать <ChevronDown className="ml-1 h-4 w-4" />
                        </>
                      ) : (
                        <>
                          Скрыть <ChevronUp className="ml-1 h-4 w-4" />
                        </>
                      )}
                    </Button>
                  </div>
                  {!warningsCollapsed && (
                    <AlertDescription>
                      <ul className="mt-2 max-h-80 space-y-1 overflow-y-auto text-sm">
                        {result.warnings.map((warning, index) => (
                          <li key={index} className="border-b border-dashed pb-1 last:border-0">
                            {warning.message}
                          </li>
                        ))}
                      </ul>
                    </AlertDescription>
                  )}
                </Alert>
              )}

              {isSuccess && (
                <Button onClick={handleDownload} disabled={isDownloading} className="w-full sm:w-auto">
                  {isDownloading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Формирование файла...
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4" />
                      Скачать расписание (.docx)
                    </>
                  )}
                </Button>
              )}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
};

export default App;
