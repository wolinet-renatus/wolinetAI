'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function LaunchModelPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/launch-model/llm');
  }, [router]);

  return null;
}
