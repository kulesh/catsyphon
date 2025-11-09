import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { FileTouchedResponse, GroupedFile } from "@/types/api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Groups files touched by file path and then by change type.
 * Calculates aggregate statistics for each file and operation type.
 */
export function groupFilesByPath(
  files: FileTouchedResponse[]
): GroupedFile[] {
  const grouped = new Map<string, GroupedFile>();

  for (const file of files) {
    const { file_path, change_type, lines_added, lines_deleted, lines_modified } = file;
    const normalizedChangeType = change_type || "read";

    // Get or create file group
    if (!grouped.has(file_path)) {
      grouped.set(file_path, {
        file_path,
        total_operations: 0,
        total_lines_added: 0,
        total_lines_deleted: 0,
        total_lines_modified: 0,
        operations: {},
      });
    }

    const fileGroup = grouped.get(file_path)!;

    // Get or create operation group within this file
    if (!fileGroup.operations[normalizedChangeType]) {
      fileGroup.operations[normalizedChangeType] = {
        change_type: normalizedChangeType,
        count: 0,
        total_lines_added: 0,
        total_lines_deleted: 0,
        total_lines_modified: 0,
        modifications: [],
      };
    }

    const operationGroup = fileGroup.operations[normalizedChangeType];

    // Add this modification to the operation group
    operationGroup.count += 1;
    operationGroup.total_lines_added += lines_added;
    operationGroup.total_lines_deleted += lines_deleted;
    operationGroup.total_lines_modified += lines_modified;
    operationGroup.modifications.push(file);

    // Update file-level totals
    fileGroup.total_operations += 1;
    fileGroup.total_lines_added += lines_added;
    fileGroup.total_lines_deleted += lines_deleted;
    fileGroup.total_lines_modified += lines_modified;
  }

  // Convert map to array and sort by file path
  return Array.from(grouped.values()).sort((a, b) =>
    a.file_path.localeCompare(b.file_path)
  );
}
