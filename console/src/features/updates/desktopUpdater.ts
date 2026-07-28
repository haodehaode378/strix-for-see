export type UpdateProgress = {
  downloadedBytes: number;
  totalBytes: number;
};

export function isDesktopRuntime(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export async function installDesktopUpdate(
  onProgress: (progress: UpdateProgress) => void,
): Promise<void> {
  if (!isDesktopRuntime()) {
    throw new Error("desktopOnly");
  }
  const { check } = await import("@tauri-apps/plugin-updater");
  const update = await check();
  if (!update) {
    throw new Error("updateUnavailable");
  }
  let downloadedBytes = 0;
  let totalBytes = 0;
  await update.downloadAndInstall((event) => {
    if (event.event === "Started") {
      totalBytes = event.data.contentLength ?? 0;
    } else if (event.event === "Progress") {
      downloadedBytes += event.data.chunkLength;
      onProgress({ downloadedBytes, totalBytes });
    } else if (event.event === "Finished") {
      onProgress({ downloadedBytes: totalBytes, totalBytes });
    }
  });
}
