import { notFound } from "next/navigation";
import { DigestView } from "@/components/content/DigestView";
import { summariesServer } from "@/lib/api-server";

export default async function MonthlyPage({ params }: { params: Promise<{ yearMonth: string }> }) {
  const { yearMonth } = await params;

  let data;
  try {
    data = await summariesServer.monthly(yearMonth);
  } catch {
    notFound();
  }

  const [year, month] = yearMonth.split("-");
  const title = `${year}년 ${month}월`;

  return (
    <DigestView
      title={title}
      subtitle="월간 다이제스트"
      content={data.content_md ?? "요약이 아직 생성되지 않았습니다."}
    />
  );
}
