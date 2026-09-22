import { useEffect, useState } from "react";

export function NetworkStatus() {
  const [online, setOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  if (online) return null;
  return (
    <div className="network-banner" role="status">
      인터넷 연결이 끊겼어요. 편집 중인 내용은 초안 저장을 확인한 뒤 다시 시도해주세요.
    </div>
  );
}
