import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, FileSpreadsheet, FileText, Loader2, Sparkles } from "lucide-react";

export interface SelectedFiles {
  upNoo: File | null;
  upOoo: File | null;
  upSoo: File | null;
  workload: File | null;
}

interface ScheduleFormProps {
  isLoading: boolean;
  onSubmit: (files: {
    upNoo: File;
    upOoo: File;
    upSoo: File;
    workload: File;
  }) => void;
}

export const ScheduleForm: React.FC<ScheduleFormProps> = ({
  isLoading,
  onSubmit,
}) => {
  const [files, setFiles] = useState<SelectedFiles>({
    upNoo: null,
    upOoo: null,
    upSoo: null,
    workload: null,
  });

  const [validationError, setValidationError] = useState<string | null>(null);

  const handleFileChange = (
    field: keyof SelectedFiles,
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0] || null;
    setFiles((prev) => ({ ...prev, [field]: file }));
    setValidationError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!files.upNoo || !files.upOoo || !files.upSoo || !files.workload) {
      setValidationError("Пожалуйста, выберите все 4 обязательных файла перед запуском генерации.");
      return;
    }

    setValidationError(null);
    onSubmit({
      upNoo: files.upNoo,
      upOoo: files.upOoo,
      upSoo: files.upSoo,
      workload: files.workload,
    });
  };

  return (
    <Card className="w-full shadow-md">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <CardTitle className="text-xl">Загрузка документов школы</CardTitle>
        </div>
        <CardDescription>
          Выберите три файла учебных планов (.docx) и таблицу педагогической нагрузки (.xlsx)
        </CardDescription>
      </CardHeader>

      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-5">
          {validationError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Не все файлы выбраны</AlertTitle>
              <AlertDescription>{validationError}</AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* УП НОО */}
            <div className="space-y-2 rounded-lg border p-3.5 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-600" />
                <Label htmlFor="up-noo" className="font-semibold text-slate-800">
                  Учебный план НОО (1–4 классы) <span className="text-red-500">*</span>
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">Файл документа Word (.docx)</p>
              <Input
                id="up-noo"
                type="file"
                accept=".docx"
                required
                disabled={isLoading}
                onChange={(e) => handleFileChange("upNoo", e)}
                className="bg-white cursor-pointer"
              />
            </div>

            {/* УП ООО */}
            <div className="space-y-2 rounded-lg border p-3.5 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-600" />
                <Label htmlFor="up-ooo" className="font-semibold text-slate-800">
                  Учебный план ООО (5–9 классы) <span className="text-red-500">*</span>
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">Файл документа Word (.docx)</p>
              <Input
                id="up-ooo"
                type="file"
                accept=".docx"
                required
                disabled={isLoading}
                onChange={(e) => handleFileChange("upOoo", e)}
                className="bg-white cursor-pointer"
              />
            </div>

            {/* УП СОО */}
            <div className="space-y-2 rounded-lg border p-3.5 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-600" />
                <Label htmlFor="up-soo" className="font-semibold text-slate-800">
                  Учебный план СОО (10–11 классы) <span className="text-red-500">*</span>
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">Файл документа Word (.docx)</p>
              <Input
                id="up-soo"
                type="file"
                accept=".docx"
                required
                disabled={isLoading}
                onChange={(e) => handleFileChange("upSoo", e)}
                className="bg-white cursor-pointer"
              />
            </div>

            {/* Нагрузка */}
            <div className="space-y-2 rounded-lg border p-3.5 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
                <Label htmlFor="workload" className="font-semibold text-slate-800">
                  Нагрузка учителей <span className="text-red-500">*</span>
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">Таблица Excel (.xlsx)</p>
              <Input
                id="workload"
                type="file"
                accept=".xlsx,.xls"
                required
                disabled={isLoading}
                onChange={(e) => handleFileChange("workload", e)}
                className="bg-white cursor-pointer"
              />
            </div>
          </div>
        </CardContent>

        <CardFooter className="flex justify-end pt-2">
          <Button
            type="submit"
            size="lg"
            disabled={isLoading}
            className="w-full sm:w-auto font-medium"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Генерация расписания...
              </>
            ) : (
              "Сгенерировать расписание"
            )}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
};
