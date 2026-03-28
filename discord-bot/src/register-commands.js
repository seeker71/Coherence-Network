/**
 * Register Discord slash commands with the Discord API.
 * Run once: node src/register-commands.js
 */

import { REST, Routes } from 'discord.js';
import dotenv from 'dotenv';
dotenv.config();

import { data as ccIdea } from './commands/cc-idea.js';
import { data as ccStatus } from './commands/cc-status.js';
import { data as ccStake } from './commands/cc-stake.js';

const TOKEN = process.env.DISCORD_TOKEN;
const CLIENT_ID = process.env.DISCORD_CLIENT_ID;
const GUILD_ID = process.env.DISCORD_GUILD_ID;

if (!TOKEN || !CLIENT_ID) {
  console.error('DISCORD_TOKEN and DISCORD_CLIENT_ID must be set');
  process.exit(1);
}

const rest = new REST().setToken(TOKEN);
const commands = [ccIdea, ccStatus, ccStake].map(cmd => cmd.toJSON());

try {
  if (GUILD_ID) {
    await rest.put(Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID), { body: commands });
    console.log(`Registered ${commands.length} guild commands in guild ${GUILD_ID}`);
  } else {
    await rest.put(Routes.applicationCommands(CLIENT_ID), { body: commands });
    console.log(`Registered ${commands.length} global commands`);
  }
} catch (err) {
  console.error('Failed to register commands:', err);
  process.exit(1);
}
