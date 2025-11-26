import NextAuth from "next-auth"
import TwitterProvider from "next-auth/providers/twitter"

export const authOptions = {
  providers: [
    TwitterProvider({
      clientId: process.env.TWITTER_CLIENT_ID || "",
      clientSecret: process.env.TWITTER_CLIENT_SECRET || "",
      version: "2.0", // opt-in to Twitter OAuth 2.0
    }),
  ],
  callbacks: {
    async session({ session, token, user }) {
      session.user.id = token.sub;
      return session;
    },
  },
}

export default NextAuth(authOptions)
