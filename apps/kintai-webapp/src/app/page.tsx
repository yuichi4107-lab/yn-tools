import { PageLayout, Card } from "@yn-tools/ui";

export default function Home() {
  return (
    <PageLayout title="勤怠管理Webアプリ">
      <Card title="ダッシュボード">
        <p>勤怠データの集計・管理を行うWebアプリです。</p>
        <p style={{ color: "#16a34a", fontWeight: "bold" }}>✓ 自動デプロイ動作確認済み</p>
      </Card>
      <Card title="機能一覧（移行予定）">
        <ul>
          <li>CSVアップロード・勤怠集計</li>
          <li>従業員別月間レポート</li>
          <li>datファイル出力</li>
        </ul>
      </Card>
    </PageLayout>
  );
}
