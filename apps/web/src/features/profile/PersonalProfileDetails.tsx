import type { PersonalProfile } from "../../lib/api/types";

export function PersonalProfileDetails({ profile }: { profile: PersonalProfile }) {
  return (
    <dl className="profile-definition-list">
      <div>
        <dt>Team or business area</dt>
        <Value value={profile.profileTeam} />
      </div>
      <div>
        <dt>Rank or grade</dt>
        <Value value={profile.rankOrGrade} />
      </div>
      <div>
        <dt>Service number</dt>
        <Value className="mono-ref" value={profile.serviceNumber} />
      </div>
      <div>
        <dt>Operational skills</dt>
        {profile.skills.length ? (
          <dd>
            <ul className="profile-skill-list">
              {profile.skills.map((skill) => (
                <li key={skill}>{skill}</li>
              ))}
            </ul>
          </dd>
        ) : (
          <Value value={null} />
        )}
      </div>
      <div>
        <dt>Additional information</dt>
        <Value className="profile-definition-list__prose" value={profile.additionalInformation} />
      </div>
    </dl>
  );
}

function Value({ className, value }: { className?: string; value: string | null }) {
  if (!value) return <dd className="profile-definition-list__empty">Not provided</dd>;
  return <dd className={className}>{value}</dd>;
}
