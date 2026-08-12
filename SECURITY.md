# Security and sensitive-data reporting

Do not report suspected participant, patient, or institutional identifying information in a public GitHub issue, discussion, commit, or pull request.

If restricted PhysioNet material may permit identification, stop handling or sharing it and follow the applicable PhysioNet agreement. The current Restricted/Credentialed Health Data agreements direct users to report the specific location to `PHI-report@physionet.org`.

For a repository-only secret exposure, revoke the credential first, remove it from the public surface, and contact the repository owner privately through GitHub. Deleting a file in a later commit does not remove it from Git history.

The automated release checker is defense in depth; it cannot prove that arbitrary content is non-identifying.
