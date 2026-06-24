import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import LandingPage from "./pages/LandingPage";
import GeneratedModel from "./pages/GeneratedModel";
import OrderKit from "./pages/OrderKit";
import Success from "./pages/Success";
import { InstructionsPage } from "./pages/InstructionsPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import UserDashboard from "./pages/UserDashboard"; // NEW
import CommunityPage from "./pages/CommunityPage";
import CompetitionsPage from "./pages/CompetitionsPage";
import { AnnouncementBanner } from "./components/AnnouncementBanner";
// import { ProtectedRoute } from "./components/ProtectedRoute";

function ExternalRedirect({ to }: { to: string }) {
  if (typeof window !== "undefined") {
    window.location.replace(to);
  }
  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      {/* <ProtectedRoute> */}
        {/* <AnnouncementBanner /> */}
        <Routes>
          {/* Public */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/landing" element={<Navigate to="/" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* App pages */}
          <Route path="/dashboard" element={<UserDashboard />} /> {/* NEW */}
          <Route path="/generated-model" element={<GeneratedModel />} />
          <Route path="/instructions" element={<InstructionsPage />} />
          <Route path="/order" element={<OrderKit />} />
          <Route path="/success" element={<Success />} />
          <Route path="/community" element={<CommunityPage />} />
          <Route path="/competitions" element={<CompetitionsPage />} />

          {/* External redirects */}
          <Route
            path="/brickworld26"
            element={
              <ExternalRedirect to="https://docs.google.com/presentation/d/1oI4e2VkhY3XyYzyPsceF538b2fIle7ZknC3XZzzUl-Y/edit?usp=sharing" />
            }
          />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      {/* </ProtectedRoute> */}
    </BrowserRouter>
  );
}
