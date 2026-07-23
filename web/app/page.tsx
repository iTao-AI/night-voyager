import { PortfolioEntry } from "../components/presentation/PortfolioEntry";
import { PortfolioShell } from "../components/presentation/PortfolioShell";

export default function Home() {
  return (
    <PortfolioShell>
      <PortfolioEntry />
    </PortfolioShell>
  );
}
