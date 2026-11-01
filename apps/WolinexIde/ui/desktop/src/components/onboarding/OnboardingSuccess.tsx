import { Button } from '../ui/button';
import {
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  Zap,
  Cpu,
  Lock,
} from 'lucide-react';

interface OnboardingSuccessProps {
  providerName: string;
  onFinish: (telemetryEnabled: boolean) => void;
}

export default function OnboardingSuccess({
  providerName,
  onFinish,
}: OnboardingSuccessProps) {
  const telemetryOptIn = false;

  const displayProvider =
    providerName === 'litellm'
      ? 'Wolinex Sovereign AI Gateway'
      : providerName || 'Wolinex Sovereign AI Gateway';

  return (
    <div className="h-screen w-full bg-[#101216] text-gray-200 overflow-hidden flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#181a1d] border border-[#2a2d35] rounded-2xl p-8 shadow-2xl flex flex-col items-center text-center animate-fadeIn">
        {/* Success Icon */}
        <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-5 text-emerald-400 shadow-xl shadow-emerald-500/10">
          <CheckCircle2 className="w-8 h-8" />
        </div>

        <h2 className="text-2xl font-bold text-white tracking-tight mb-2">
          Workstation Connected
        </h2>
        <p className="text-xs text-gray-400 leading-relaxed mb-6">
          Wolinex AI Workstation is securely paired with{' '}
          <span className="text-blue-400 font-medium">{displayProvider}</span>.
        </p>

        {/* Status Highlights */}
        <div className="w-full bg-[#101216] border border-[#252831] rounded-xl p-4 flex flex-col gap-3 text-left mb-6">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-blue-400" />
              Gateway Engine
            </span>
            <span className="text-gray-200 font-semibold font-mono">Wolinex Neural Core</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              Sovereign Routing
            </span>
            <span className="text-gray-200 font-semibold font-mono">Active</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              Privacy Enforcement
            </span>
            <span className="text-emerald-400 font-semibold">Zero Data Leakage</span>
          </div>
        </div>

        {/* Security / Telemetry Notice */}
        <div className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg bg-[#14161a] border border-[#22252d] text-left text-xs mb-6">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-gray-300">Third-party telemetry disabled</span>
          </div>
          <span className="text-[10px] text-gray-500 font-mono">SOVEREIGN</span>
        </div>

        {/* Launch Button */}
        <Button
          onClick={() => onFinish(telemetryOptIn)}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2.5 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 transition-all text-sm"
        >
          <span>Launch Workstation</span>
          <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
