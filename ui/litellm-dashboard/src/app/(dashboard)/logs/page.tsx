"use client";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import RequestLogsPage from "@/components/view_logs";

export default function LogsPage() {
  const { accessToken, token, userRole, userId, premiumUser } = useAuthorized();

  return (
    <RequestLogsPage
      accessToken={accessToken}
      token={token}
      userRole={userRole}
      userID={userId}
      premiumUser={premiumUser}
    />
  );
}
