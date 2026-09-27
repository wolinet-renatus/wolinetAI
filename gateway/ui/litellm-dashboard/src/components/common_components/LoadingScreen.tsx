import { cx } from "@/lib/cva.config";
import { UiLoadingSpinner } from "../ui/ui-loading-spinner";

export default function LoadingScreen() {
  return (
    <div className={cx("h-screen", "flex items-center justify-center gap-4")}>
      <div className="flex items-center gap-2.5 py-2 pr-4 border-r border-border">
        <img src="/get_image" alt="Wolinet AI" className="h-7 w-7 object-contain dark:hidden" />
        <img src="/get_image?theme=dark" alt="Wolinet AI" className="h-7 w-7 object-contain hidden dark:block" />
        <span className="text-base font-bold text-foreground tracking-tight">Wolinet AI</span>
      </div>

      <div className="flex items-center justify-center gap-2">
        <UiLoadingSpinner className="size-4" />
        <span className="text-muted-foreground text-sm">Loading...</span>
      </div>
    </div>
  );
}

