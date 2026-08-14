import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "../../lib/api/client";
import type { OrganisationUnit } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";

export function RenameOrganisationUnit({ unit }: { unit: OrganisationUnit }) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(unit.name);
  const mutation = useMutation({
    mutationFn: () =>
      api.renameOrganisationUnit(
        unit.id,
        { name: name.trim(), expectedVersion: unit.version },
        session!.csrfToken,
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData<{ items: OrganisationUnit[] }>(
        queryKeys.organisationUnits(),
        (current) => ({
          items: current!.items.map((candidate) => (candidate.id === saved.id ? saved : candidate)),
        }),
      );
      setEditing(false);
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (name.trim().length >= 2) mutation.mutate();
  };
  if (!editing)
    return (
      <button
        aria-label={`Rename ${unit.name}`}
        className="button button--quiet organisation-rename-trigger"
        onClick={() => {
          setName(unit.name);
          mutation.reset();
          setEditing(true);
        }}
        type="button"
      >
        Rename
      </button>
    );
  const invalid = name.trim().length < 2;
  return (
    <form className="organisation-rename" onSubmit={submit}>
      <label className="form-field">
        <span className="sr-only">New name for {unit.name}</span>
        <input
          aria-invalid={invalid}
          autoFocus
          maxLength={120}
          onChange={(event) => setName(event.target.value)}
          value={name}
        />
      </label>
      <button
        className="button button--primary"
        disabled={invalid || mutation.isPending}
        type="submit"
      >
        Save
      </button>
      <button
        className="button button--quiet"
        onClick={() => {
          mutation.reset();
          setEditing(false);
        }}
        type="button"
      >
        Cancel
      </button>
      {invalid ? (
        <small className="field-error" role="alert">
          Enter at least two characters.
        </small>
      ) : null}
      {mutation.isError ? (
        <small className="field-error" role="alert">
          {mutation.error instanceof ApiError
            ? mutation.error.message
            : "The unit could not be renamed."}
        </small>
      ) : null}
    </form>
  );
}
