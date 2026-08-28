"use client";

import { updateBranch } from "../api/update-branch";
import { BranchSaveDialog } from "./BranchSaveDialog";
import type { Branch } from "../types";

interface Props {
  branch: Branch;
  onClose: () => void;
  onUpdated: (branch: Branch) => void;
}

export function EditBranchDialog({ branch, onClose, onUpdated }: Props) {
  return (
    <BranchSaveDialog
      title="Edit branch"
      initialDraft={{ code: branch.code, name: branch.name, locationId: branch.location_id }}
      onClose={onClose}
      onSaved={onUpdated}
      onSave={(draft) =>
        updateBranch(branch.id, { code: draft.code, name: draft.name, location_id: draft.locationId })
      }
    />
  );
}
