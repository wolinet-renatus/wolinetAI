import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "../../../../tests/test-utils";
import { CommunityEngagementButtons } from "./CommunityEngagementButtons";

let mockUseDisableShowPromptsImpl = () => false;

vi.mock("@/app/(dashboard)/hooks/useDisableShowPrompts", () => ({
  useDisableShowPrompts: () => mockUseDisableShowPromptsImpl(),
}));

describe("CommunityEngagementButtons", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDisableShowPromptsImpl = () => false;
  });

  it("should render", () => {
    renderWithProviders(<CommunityEngagementButtons />);
    expect(screen.getByRole("link", { name: /wolinet ai website/i })).toBeInTheDocument();
  });

  it("should render the Wolinet website button with the correct link", () => {
    renderWithProviders(<CommunityEngagementButtons />);

    const websiteLink = screen.getByRole("link", { name: /wolinet ai website/i });
    expect(websiteLink).toBeInTheDocument();
    expect(websiteLink).toHaveAttribute("href", "https://ai.wolinet.com");
    expect(websiteLink).toHaveAttribute("target", "_blank");
    expect(websiteLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("should render GitHub link with correct href", () => {
    renderWithProviders(<CommunityEngagementButtons />);

    const githubLink = screen.getByRole("link", { name: /wolinet ai on github/i });
    expect(githubLink).toBeInTheDocument();
    expect(githubLink).toHaveAttribute("href", "https://github.com/wolinet-renatus/wolinetAI");
    expect(githubLink).toHaveAttribute("target", "_blank");
    expect(githubLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("should not render buttons when prompts are disabled", () => {
    mockUseDisableShowPromptsImpl = () => true;

    renderWithProviders(<CommunityEngagementButtons />);

    expect(screen.queryByRole("link", { name: /wolinet ai website/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /wolinet ai on github/i })).not.toBeInTheDocument();
  });
});
