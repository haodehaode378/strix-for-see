use rand::{Rng, distr::Alphanumeric};
use std::{
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
};
use tauri::{
    AppHandle, Emitter, Manager,
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
};

struct SidecarState {
    bootstrap_token: String,
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn get_bootstrap_token(state: tauri::State<'_, SidecarState>) -> String {
    state.bootstrap_token.clone()
}

#[tauri::command]
fn exit_app(app: AppHandle, state: tauri::State<'_, SidecarState>) {
    if let Ok(mut child) = state.child.lock()
        && let Some(mut process) = child.take()
    {
        let _ = process.kill();
        let _ = process.wait();
    }
    app.exit(0);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let access_token = random_token();
    let bootstrap_token = random_token();
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(SidecarState {
            bootstrap_token: bootstrap_token.clone(),
            child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![exit_app, get_bootstrap_token])
        .setup(move |app| {
            if let Some(service_path) = resolve_sidecar_path() {
                let strix_path = service_path.with_file_name("strix.exe");
                let mut command = Command::new(service_path);
                command
                    .arg("--parent-pid")
                    .arg(std::process::id().to_string())
                    .env("STRIX_CONSOLE_ACCESS_TOKEN", &access_token)
                    .env("STRIX_CONSOLE_BOOTSTRAP_TOKEN", &bootstrap_token)
                    .env("STRIX_CONSOLE_STRIX_PATH", strix_path);
                #[cfg(windows)]
                {
                    use std::os::windows::process::CommandExt;
                    command.creation_flags(0x08000000);
                }
                let child = command.spawn()?;
                *app.state::<SidecarState>()
                    .child
                    .lock()
                    .map_err(|_| "sidecarStateUnavailable")? = Some(child);
            }
            let open = MenuItem::with_id(app, "open", "Open Strix Console", true, None::<&str>)?;
            let stop = MenuItem::with_id(app, "stop", "Stop active scan", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Exit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &stop, &quit])?;
            let mut tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("Strix Console")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "stop" => {
                        let _ = app.emit("tray-stop-scan", ());
                    }
                    "quit" => {
                        let _ = app.emit("tray-exit-request", ());
                    }
                    _ => {}
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to run Strix Console");
}

fn random_token() -> String {
    rand::rng()
        .sample_iter(&Alphanumeric)
        .take(48)
        .map(char::from)
        .collect()
}

fn resolve_sidecar_path() -> Option<PathBuf> {
    if let Some(configured) = std::env::var_os("STRIX_CONSOLE_SERVICE_PATH") {
        let path = PathBuf::from(configured);
        return path.is_file().then_some(path);
    }
    let path = std::env::current_exe()
        .ok()?
        .parent()?
        .join("strix-console-service.exe");
    path.is_file().then_some(path)
}
