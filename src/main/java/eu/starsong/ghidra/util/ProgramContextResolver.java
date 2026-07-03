package eu.starsong.ghidra.util;

import ghidra.app.services.ProgramManager;
import ghidra.framework.model.Project;
import ghidra.framework.model.ToolManager;
import ghidra.framework.plugintool.PluginTool;
import ghidra.program.model.listing.Program;

/**
 * Resolves the active program across all running Ghidra tools in the project.
 * FrontEnd (8192) often has no current program while a CodeBrowser holds the binary.
 */
public final class ProgramContextResolver {

    private ProgramContextResolver() {
    }

    public static Program findOpenProgram(PluginTool localTool) {
        Program local = localProgram(localTool);
        if (local != null) {
            return local;
        }
        Project project = localTool != null ? localTool.getProject() : null;
        if (project == null) {
            return null;
        }
        ToolManager toolManager = project.getToolManager();
        if (toolManager == null) {
            return null;
        }
        for (PluginTool running : toolManager.getRunningTools()) {
            if (running == localTool) {
                continue;
            }
            Program found = currentFromTool(running);
            if (found != null) {
                return found;
            }
        }
        return null;
    }

    /** Program open in this tool only (no cross-tool fallback). */
    public static Program localProgram(PluginTool tool) {
        return currentFromTool(tool);
    }

    public static PluginTool findToolWithOpenProgram(PluginTool localTool) {
        if (localProgram(localTool) != null) {
            return localTool;
        }
        Project project = localTool != null ? localTool.getProject() : null;
        if (project == null) {
            return null;
        }
        ToolManager toolManager = project.getToolManager();
        if (toolManager == null) {
            return null;
        }
        for (PluginTool running : toolManager.getRunningTools()) {
            if (running != localTool && currentFromTool(running) != null) {
                return running;
            }
        }
        return null;
    }

    private static Program currentFromTool(PluginTool tool) {
        if (tool == null) {
            return null;
        }
        ProgramManager pm = tool.getService(ProgramManager.class);
        if (pm == null) {
            return null;
        }
        Program current = pm.getCurrentProgram();
        if (current != null) {
            return current;
        }
        Program[] open = pm.getAllOpenPrograms();
        if (open != null && open.length > 0) {
            return open[0];
        }
        return null;
    }
}
