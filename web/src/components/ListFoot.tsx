"use client";

import { DownloadButton } from "./DownloadButton";
import { ShowMore } from "./ui/kit";

/** Under every paged list: how many rows match, Show more, and the list as a CSV file with
 *  the same search, filters and sort (UX_FLOWS "Long lists"). */
export function ListFoot({
  hasMore,
  more,
  shown,
  total,
  exportPath,
}: {
  hasMore: boolean;
  more: () => void;
  shown?: number;
  total: number | null;
  exportPath: string | null;
}) {
  return (
    <ShowMore hasMore={hasMore} more={more} shown={shown} total={total}>
      {exportPath && total ? <DownloadButton path={exportPath}>Export CSV</DownloadButton> : null}
    </ShowMore>
  );
}
