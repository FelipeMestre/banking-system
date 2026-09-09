"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createAccount } from "../api/create-account";
import type { Account, FirstAccountKyc } from "../types";

interface Props {
  onClose: () => void;
  onSuccess: (account: Account) => void;
  /** True only when the caller's Auth0 identity has no linked Customer yet
   * (the "no customer linked" signal from `HomeDashboard`) — in that case the
   * dialog also collects the KYC fields `POST /accounts/me` needs to auto-link
   * the identity. False (the default) covers the already-linked, zero-accounts
   * case, unchanged from the original shipped behavior. */
  requiresKyc?: boolean;
}

type KycForm = {
  identification_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
};

const EMPTY_KYC_FORM: KycForm = {
  identification_number: "",
  first_name: "",
  last_name: "",
  date_of_birth: "",
};

function isKycFormComplete(form: KycForm): boolean {
  return Object.values(form).every((value) => value.trim().length > 0);
}

/**
 * Terms & Conditions gate in front of `POST /accounts/me`. Decline closes
 * with no request at all (spec — Decline has no side effects); Accept is the
 * only path that calls `createAccount`. A failure (e.g. a concurrent-request
 * 409) shows inline and never retries automatically or throws past this
 * component (spec — creation fails with 409 due to a race).
 *
 * When `requiresKyc` is true, the required identity fields render above the
 * T&C copy and Accept stays disabled until every one of them is filled
 * client-side (a final 422 is still possible — the backend is the source of
 * truth — this is only a fast, local check).
 */
export function CreateAccountDialog({ onClose, onSuccess, requiresKyc = false }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kycForm, setKycForm] = useState<KycForm>(EMPTY_KYC_FORM);

  function handleAccept() {
    setError(null);
    setPending(true);
    const kyc: FirstAccountKyc | undefined = requiresKyc ? { ...kycForm } : undefined;
    createAccount(kyc)
      .then((account) => {
        onSuccess(account);
      })
      .catch((caught: unknown) => {
        setPending(false);
        setError(caught instanceof Error ? caught.message : "Could not create the account.");
      });
  }

  function updateField(field: keyof KycForm) {
    return (event: React.ChangeEvent<HTMLInputElement>) => {
      setKycForm((current) => ({ ...current, [field]: event.target.value }));
    };
  }

  const acceptDisabled = pending || (requiresKyc && !isKycFormComplete(kycForm));

  return (
    <Dialog
      title="Terms and Conditions"
      onClose={onClose}
      onAccept={handleAccept}
      acceptLabel="Accept and open account"
      cancelLabel="Decline"
      acceptDisabled={acceptDisabled}
    >
      <div className="flex flex-col gap-ds-3">
        {requiresKyc ? (
          <div className="flex flex-col gap-ds-3">
            <div className="field">
              <Label htmlFor="kyc-identification-number">Identification number</Label>
              <Input
                id="kyc-identification-number"
                value={kycForm.identification_number}
                onChange={updateField("identification_number")}
                autoComplete="off"
                autoFocus
              />
            </div>
            <div className="field">
              <Label htmlFor="kyc-first-name">First name</Label>
              <Input id="kyc-first-name" value={kycForm.first_name} onChange={updateField("first_name")} />
            </div>
            <div className="field">
              <Label htmlFor="kyc-last-name">Last name</Label>
              <Input id="kyc-last-name" value={kycForm.last_name} onChange={updateField("last_name")} />
            </div>
            <div className="field">
              <Label htmlFor="kyc-date-of-birth">Date of birth</Label>
              <Input
                id="kyc-date-of-birth"
                type="date"
                value={kycForm.date_of_birth}
                onChange={updateField("date_of_birth")}
              />
            </div>
          </div>
        ) : null}
        <p className="m-0">
          Your new account is opened in USD only. By continuing, you agree to the deposit
          agreement and fee schedule, and you confirm that your identity has already been
          verified with us.
        </p>
        <p className="m-0">
          An account left with a zero balance may be closed after a period of inactivity.
        </p>
        {error ? <ErrorMessage message={error} /> : null}
      </div>
    </Dialog>
  );
}
