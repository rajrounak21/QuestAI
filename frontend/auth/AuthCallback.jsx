import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { storeRefresh, storeToken } from "./api";
import AuthLayout from "./components/AuthLayout";
import { AuthCard, Notice } from "./components/ui";

// Route this at /auth/callback in your React router.
// Backend redirects here as: /auth/callback#token=<jwt>&refresh=<jwt>
export default function AuthCallback() {
  const navigate = useNavigate();
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1)); // #token=xxx&refresh=yyy
    const token = params.get("token");
    const refresh = params.get("refresh");
    if (token) {
      storeToken(token);
      if (refresh) storeRefresh(refresh);
      navigate("/home", { replace: true });
    } else {
      setNotice({ kind: "err", text: "No token found in URL." });
    }
  }, [navigate]);

  return (
    <AuthLayout>
      <AuthCard title="Google callback" subtitle="Finishing sign-in.">
        <Notice kind={notice?.kind}>{notice?.text}</Notice>
      </AuthCard>
    </AuthLayout>
  );
}
