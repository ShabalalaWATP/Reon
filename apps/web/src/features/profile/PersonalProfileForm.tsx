import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { PersonalProfile, PersonalProfileUpdate } from "../../lib/api/types";

const schema = z.object({
  profileTeam: z.string().trim().max(120, "Use 120 characters or fewer."),
  rankOrGrade: z.string().trim().max(120, "Use 120 characters or fewer."),
  serviceNumber: z.string().trim().max(80, "Use 80 characters or fewer."),
  additionalInformation: z.string().trim().max(2000, "Use 2,000 characters or fewer."),
});
type Values = z.infer<typeof schema>;

export function PersonalProfileForm({
  disabled,
  onSubmit,
  profile,
}: {
  disabled: boolean;
  onSubmit: (value: PersonalProfileUpdate) => void;
  profile: PersonalProfile;
}) {
  const { formState: { errors, isDirty, isValid }, handleSubmit, register } = useForm<Values>({
    defaultValues: {
      profileTeam: profile.profileTeam ?? "",
      rankOrGrade: profile.rankOrGrade ?? "",
      serviceNumber: profile.serviceNumber ?? "",
      additionalInformation: profile.additionalInformation ?? "",
    },
    mode: "onChange",
    resolver: zodResolver(schema),
  });
  const nullable = (value: string) => value.trim() || null;
  return <form className="profile-form" noValidate onSubmit={(event) => void handleSubmit((values) => onSubmit({
    profileTeam: nullable(values.profileTeam),
    rankOrGrade: nullable(values.rankOrGrade),
    serviceNumber: nullable(values.serviceNumber),
    additionalInformation: nullable(values.additionalInformation),
    expectedVersion: profile.version,
  }))(event)}>
    <div className="profile-form__grid">
      <label className="form-field"><span>Team or business area</span><input aria-invalid={Boolean(errors.profileTeam)} {...register("profileTeam")} />{errors.profileTeam ? <small role="alert">{errors.profileTeam.message}</small> : <small>Your own team or area, not an ISTARI routing choice.</small>}</label>
      <label className="form-field"><span>Rank or grade</span><input aria-invalid={Boolean(errors.rankOrGrade)} {...register("rankOrGrade")} />{errors.rankOrGrade ? <small role="alert">{errors.rankOrGrade.message}</small> : null}</label>
      <label className="form-field"><span>Service number</span><input aria-invalid={Boolean(errors.serviceNumber)} autoComplete="off" {...register("serviceNumber")} />{errors.serviceNumber ? <small role="alert">{errors.serviceNumber.message}</small> : <small>Visible only in your personal profile.</small>}</label>
    </div>
    <label className="form-field"><span>Additional information</span><textarea aria-invalid={Boolean(errors.additionalInformation)} rows={5} {...register("additionalInformation")} />{errors.additionalInformation ? <small role="alert">{errors.additionalInformation.message}</small> : <small>Add any context that helps colleagues understand who you are. Do not enter passwords or sensitive operational content.</small>}</label>
    <button className="button button--primary" disabled={disabled || !isDirty || !isValid} type="submit">{disabled ? "Saving…" : "Save personal details"}</button>
  </form>;
}
