import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { PersonalProfile, PersonalProfileUpdate } from "../../lib/api/types";

const schema = z.object({
  profileTeam: z.string().trim().max(120, "Use 120 characters or fewer."),
  rankOrGrade: z.string().trim().max(120, "Use 120 characters or fewer."),
  serviceNumber: z.string().trim().max(80, "Use 80 characters or fewer."),
  skills: z
    .string()
    .trim()
    .max(960, "Use no more than 12 short skills.")
    .superRefine((value, context) => {
      const labels = parseSkills(value);
      if (labels.length > 12)
        context.addIssue({ code: "custom", message: "Use no more than 12 skills." });
      if (labels.some((label) => label.length > 80))
        context.addIssue({ code: "custom", message: "Use 80 characters or fewer for each skill." });
      if (new Set(labels.map((label) => label.toLocaleLowerCase("en-GB"))).size !== labels.length)
        context.addIssue({ code: "custom", message: "List each skill once." });
    }),
  additionalInformation: z.string().trim().max(2000, "Use 2,000 characters or fewer."),
});
type Values = z.infer<typeof schema>;

export function PersonalProfileForm({
  disabled,
  onCancel,
  onSubmit,
  profile,
}: {
  disabled: boolean;
  onCancel?: () => void;
  onSubmit: (value: PersonalProfileUpdate) => void;
  profile: PersonalProfile;
}) {
  const {
    formState: { errors, isDirty, isValid },
    handleSubmit,
    register,
  } = useForm<Values>({
    defaultValues: {
      profileTeam: profile.profileTeam ?? "",
      rankOrGrade: profile.rankOrGrade ?? "",
      serviceNumber: profile.serviceNumber ?? "",
      skills: profile.skills.join(", "),
      additionalInformation: profile.additionalInformation ?? "",
    },
    mode: "onChange",
    resolver: zodResolver(schema),
  });
  const nullable = (value: string) => value.trim() || null;
  return (
    <form
      className="profile-form"
      noValidate
      onSubmit={(event) =>
        void handleSubmit((values) =>
          onSubmit({
            profileTeam: nullable(values.profileTeam),
            rankOrGrade: nullable(values.rankOrGrade),
            serviceNumber: nullable(values.serviceNumber),
            skills: parseSkills(values.skills),
            additionalInformation: nullable(values.additionalInformation),
            expectedVersion: profile.version,
          }),
        )(event)
      }
    >
      <div className="profile-form__grid">
        <label className="form-field">
          <span>Team or business area</span>
          <input aria-invalid={Boolean(errors.profileTeam)} {...register("profileTeam")} />
          <FieldMessage
            error={errors.profileTeam?.message}
            hint="Your own team or area, not an Mist routing choice."
          />
        </label>
        <label className="form-field">
          <span>Rank or grade</span>
          <input aria-invalid={Boolean(errors.rankOrGrade)} {...register("rankOrGrade")} />
          <FieldMessage error={errors.rankOrGrade?.message} />
        </label>
        <label className="form-field">
          <span>Service number</span>
          <input
            aria-invalid={Boolean(errors.serviceNumber)}
            autoComplete="off"
            {...register("serviceNumber")}
          />
          <FieldMessage
            error={errors.serviceNumber?.message}
            hint="Visible only in your personal profile."
          />
        </label>
      </div>
      <label className="form-field">
        <span>Operational skills</span>
        <input
          aria-invalid={Boolean(errors.skills)}
          placeholder="Research, data analysis, briefing"
          {...register("skills")}
        />
        <FieldMessage
          error={errors.skills?.message}
          hint="Optional comma-separated labels for human team allocation. They are not scores or endorsements."
        />
      </label>
      <label className="form-field">
        <span>Additional information</span>
        <textarea
          aria-invalid={Boolean(errors.additionalInformation)}
          rows={5}
          {...register("additionalInformation")}
        />
        <FieldMessage
          error={errors.additionalInformation?.message}
          hint="Add any context that helps colleagues understand who you are. Do not enter passwords or sensitive operational content."
        />
      </label>
      <FormActions disabled={disabled} isDirty={isDirty} isValid={isValid} onCancel={onCancel} />
    </form>
  );
}

function FieldMessage({ error, hint }: { error?: string; hint?: string }) {
  if (error) return <small role="alert">{error}</small>;
  return hint ? <small>{hint}</small> : null;
}

function FormActions({
  disabled,
  isDirty,
  isValid,
  onCancel,
}: {
  disabled: boolean;
  isDirty: boolean;
  isValid: boolean;
  onCancel?: () => void;
}) {
  return (
    <div className="profile-form__actions">
      <button
        className="button button--primary"
        disabled={disabled || !isDirty || !isValid}
        type="submit"
      >
        {disabled ? "Saving…" : "Save personal details"}
      </button>
      {onCancel ? (
        <button
          className="button button--quiet"
          disabled={disabled}
          onClick={onCancel}
          type="button"
        >
          Cancel
        </button>
      ) : null}
    </div>
  );
}

function parseSkills(value: string) {
  return value
    .split(",")
    .map((label) => label.trim())
    .filter(Boolean);
}
