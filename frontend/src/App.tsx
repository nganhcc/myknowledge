import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { AppShell } from "./components/AppShell";
import { PublicOnly, RequireAuth } from "./components/AuthRoutes";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { ChatPage } from "./pages/ChatPage";
import { WorkspaceProvider } from "./workspaces/WorkspaceProvider";

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<PublicOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route
            element={
              <WorkspaceProvider>
                <AppShell />
              </WorkspaceProvider>
            }
          >
            <Route path="/" element={<WorkspacePage />} />
            <Route path="/workspaces" element={<WorkspacePage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
