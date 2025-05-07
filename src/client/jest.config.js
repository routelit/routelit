export default {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      useESM: true,
      tsconfig: 'tsconfig.jest.json'
    }],
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  setupFilesAfterEnv: [
    '<rootDir>/src/tests/setup.ts'
  ],
  extensionsToTreatAsEsm: ['.ts', '.tsx'],
  testMatch: ['**/src/tests/**/*.test.{ts,tsx}'],
  moduleDirectories: ['node_modules', 'src'],
  modulePaths: ['<rootDir>'],
};
