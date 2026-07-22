import { PortfolioEntry } from "../components/presentation/PortfolioEntry";
import { PresentationShell } from "../components/presentation/PresentationShell";

export default function Home() {
  return (
    <PresentationShell contextKey="contextPortfolio">
      <PortfolioEntry />
    </PresentationShell>
  );
}
